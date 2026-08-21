"""Tests for the weekly chaos-engineering CI job and its supporting files.

Validates that:
- The workflow runs on a weekly schedule with manual dispatch, safety gates
  (timeout, concurrency), a pinned Chaos Mesh install, and always() cleanup.
- Every experiment manifest is bounded in duration and targets the right app.
- Dependency manifests match the hosts referenced by the Helm overrides.
- The runner script asserts recovery and cleans up applied experiments.

Run with:  poetry run pytest tests/test_chaos_ci.py
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

CHAOS_DIR = pathlib.Path("k8s/chaos")
WORKFLOW_PATH = pathlib.Path(".github/workflows/chaos-engineering.yml")
RUNNER_PATH = pathlib.Path("scripts/run_chaos_experiments.sh")
VALUES_PATH = CHAOS_DIR / "values-chaos.yaml"
DOCS_PATH = pathlib.Path("docs/chaos.md")

EXPECTED_EXPERIMENTS = {
    "cpu-stress",
    "dns-error",
    "http-timeout",
    "network-latency",
    "pod-kill",
}


def _load_yaml(path: pathlib.Path) -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(path.read_text())  # type: ignore[no-any-return]


def _workflow_trigger(workflow: dict) -> dict:  # type: ignore[type-arg]
    """Return the `on:` mapping (PyYAML parses the key as boolean True)."""
    return workflow.get(True) or workflow["on"]  # type: ignore[no-any-return]


def _experiment_manifests() -> dict[str, dict]:  # type: ignore[type-arg]
    """Top-level experiment manifests only (deps/ subdir and Helm values excluded)."""
    manifests = {}
    for path in sorted(CHAOS_DIR.glob("*.yaml")):
        if path.name.startswith("values-"):
            continue
        manifests[path.stem] = yaml.safe_load(path.read_text())
    return manifests


# ─── Workflow structure ──────────────────────────────


class TestChaosWorkflow:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.workflow = _load_yaml(WORKFLOW_PATH)

    def _step_by_name_prefix(self, prefix: str) -> dict:  # type: ignore[type-arg]
        steps = self.workflow["jobs"]["chaos"]["steps"]
        return next(s for s in steps if str(s.get("name", "")).startswith(prefix))

    def test_workflow_exists(self) -> None:
        assert WORKFLOW_PATH.exists()

    def test_weekly_schedule(self) -> None:
        crons = [t["cron"] for t in _workflow_trigger(self.workflow)["schedule"]]
        assert "0 4 * * 0" in crons

    def test_manual_dispatch_with_experiment_input(self) -> None:
        inp = _workflow_trigger(self.workflow)["workflow_dispatch"]["inputs"]["experiments"]
        assert inp["default"] == "all"
        for name in EXPECTED_EXPERIMENTS:
            assert name in inp["description"]

    def test_safety_gates(self) -> None:
        job = self.workflow["jobs"]["chaos"]
        assert job["timeout-minutes"] <= 60
        assert self.workflow["concurrency"]["group"] == "chaos-engineering"
        assert self.workflow["concurrency"]["cancel-in-progress"] is False

    def test_kind_cluster_used(self) -> None:
        steps = self.workflow["jobs"]["chaos"]["steps"]
        kind_steps = [s for s in steps if str(s.get("uses", "")).startswith("helm/kind-action@")]
        assert len(kind_steps) == 1
        assert kind_steps[0]["with"]["cluster_name"] == "chaos-lab"

    def test_app_image_built_and_loaded(self) -> None:
        step = self._step_by_name_prefix("Build and load app image")
        run = step["run"]
        assert "Dockerfile.prod" in run
        assert "kind load docker-image" in run

    def test_helm_overrides_file_used(self) -> None:
        step = self._step_by_name_prefix("Deploy app via Helm chart")
        assert "values-chaos.yaml" in step["run"]
        assert "fastapi-template" in step["run"]

    def test_migrations_run_before_chaos(self) -> None:
        step = self._step_by_name_prefix("Run database migrations")
        assert "alembic" in step["run"]
        assert "kubectl wait" in step["run"]

    def test_readiness_verified_before_injection(self) -> None:
        step = self._step_by_name_prefix("Verify app readiness")
        assert "/healthz" in step["run"]

    def test_chaos_mesh_pinned_install(self) -> None:
        step = self._step_by_name_prefix("Install Chaos Mesh")
        run = step["run"]
        assert "--version" in run
        assert "dnsServer.create=true" in run
        assert "label namespace default chaos-mesh.org/chaos=enable" in run

    def test_runner_invoked(self) -> None:
        step = self._step_by_name_prefix("Run chaos experiments")
        assert RUNNER_PATH.name in step["run"]

    def test_diagnostics_collected_on_failure(self) -> None:
        collect = self._step_by_name_prefix("Collect diagnostics")
        upload = self._step_by_name_prefix("Upload diagnostics")
        assert collect["if"] == "always()"
        assert upload["if"] == "always()"


# ─── Experiment manifests ────────────────────────────


class TestExperimentManifests:
    def test_all_five_experiments_present(self) -> None:
        assert set(_experiment_manifests()) == EXPECTED_EXPERIMENTS

    @pytest.mark.parametrize("name", sorted(EXPECTED_EXPERIMENTS))
    def test_manifest_targets_fastapi_template(self, name: str) -> None:
        doc = _experiment_manifests()[name]
        selector = doc["spec"]["selector"]
        assert selector["labelSelectors"]["app"] == "fastapi-template"
        assert selector["namespaces"] == ["default"]

    @pytest.mark.parametrize("name", sorted(EXPECTED_EXPERIMENTS))
    def test_duration_is_bounded(self, name: str) -> None:
        doc = _experiment_manifests()[name]
        duration = int(str(doc["spec"]["duration"]).rstrip("s"))
        assert 0 < duration <= 120

    @pytest.mark.parametrize("name", sorted(EXPECTED_EXPERIMENTS))
    def test_labels_present(self, name: str) -> None:
        doc = _experiment_manifests()[name]
        labels = doc["metadata"]["labels"]
        assert labels["experiment"] == "chaos"
        assert labels["type"] == name


# ─── Dependencies & Helm overrides ───────────────────


class TestChaosDependencies:
    def test_dependency_files_exist(self) -> None:
        assert (CHAOS_DIR / "deps" / "postgres.yaml").exists()
        assert (CHAOS_DIR / "deps" / "redis.yaml").exists()

    def _service(self, filename: str, name: str) -> dict:  # type: ignore[type-arg]
        docs = [
            d
            for d in yaml.safe_load_all((CHAOS_DIR / "deps" / filename).read_text())
            if d is not None
        ]
        return next(d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == name)

    def test_postgres_service_matches_chart_host(self) -> None:
        svc = self._service("postgres.yaml", "postgres")
        assert svc["spec"]["ports"][0]["port"] == 5432

    def test_redis_service_matches_chart_host(self) -> None:
        svc = self._service("redis.yaml", "redis")
        assert svc["spec"]["ports"][0]["port"] == 6379


class TestChaosValues:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.values = _load_yaml(VALUES_PATH)

    def test_ingress_disabled(self) -> None:
        assert self.values["ingress"]["enabled"] is False

    def test_autoscaling_disabled(self) -> None:
        # No metrics-server in kind; HPA would be inert noise.
        assert self.values["autoscaling"]["enabled"] is False

    def test_image_references_locally_loaded_tag(self) -> None:
        assert self.values["image"]["tag"] == "chaos"

    def test_database_url_points_at_dep_service(self) -> None:
        url = self.values["secret"]["DATABASE_URL"]
        assert "@postgres:5432/fastapi_db" in url

    def test_redis_url_points_at_dep_service(self) -> None:
        assert self.values["config"]["REDIS_URL"].startswith("redis://redis:6379/")


# ─── Runner script ───────────────────────────────────


class TestRunnerScript:
    def test_script_exists_and_is_executable(self) -> None:
        assert RUNNER_PATH.exists()
        import stat

        mode = RUNNER_PATH.stat().st_mode
        assert mode & stat.S_IXUSR

    def test_asserts_rollout_recovery(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "rollout status" in content
        assert "RECOVERY_TIMEOUT" in content

    def test_checks_health_endpoint(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "/healthz" in content

    def test_cleans_up_applied_experiments(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "--ignore-not-found" in content
        assert "trap cleanup EXIT" in content

    def test_writes_step_summary(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "GITHUB_STEP_SUMMARY" in content

    def test_fails_on_experiment_failure(self) -> None:
        content = RUNNER_PATH.read_text()
        assert 'exit "${#FAILED[@]}"' in content

    def test_deps_dir_not_treated_as_experiment(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "-maxdepth 1" in content

    def test_helm_values_not_treated_as_experiment(self) -> None:
        content = RUNNER_PATH.read_text()
        assert "! -name 'values-*.yaml'" in content


# ─── Docs ────────────────────────────────────────────


class TestChaosDocs:
    def test_docs_page_exists(self) -> None:
        assert DOCS_PATH.exists()

    def test_docs_cover_local_reproduction(self) -> None:
        content = DOCS_PATH.read_text()
        assert "workflow_dispatch" in content or "kind" in content

    def test_readme_links_docs(self) -> None:
        readme = pathlib.Path("README.md").read_text()
        assert "docs/chaos.md" in readme
