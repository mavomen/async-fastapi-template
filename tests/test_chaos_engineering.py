"""Tests for Chaos Mesh chaos engineering manifests."""

from __future__ import annotations

import pathlib

import pytest
import yaml

CHAOS_DIR = pathlib.Path("k8s/chaos")
# Experiment manifests only: Helm value overrides (values-*.yaml) and the
# deps/ environment directory are part of the chaos setup but not Chaos CRs.
MANIFESTS = sorted(p for p in CHAOS_DIR.glob("*.yaml") if not p.name.startswith("values-"))


def _load(name: str) -> dict:  # type: ignore[type-arg]
    return yaml.safe_load((CHAOS_DIR / name).read_text())  # type: ignore[no-any-return]


class TestChaosManifestsExist:
    """All expected chaos manifests should be present."""

    @pytest.mark.parametrize(
        "name",
        [
            "pod-kill.yaml",
            "network-latency.yaml",
            "cpu-stress.yaml",
            "dns-error.yaml",
            "http-timeout.yaml",
        ],
    )
    def test_manifest_exists(self, name: str) -> None:
        assert (CHAOS_DIR / name).exists(), f"Missing chaos manifest: {name}"

    def test_at_least_five_manifests(self) -> None:
        assert len(MANIFESTS) >= 5


class TestChaosManifestSafety:
    """All chaos manifests must enforce safe defaults."""

    @pytest.fixture(params=MANIFESTS, ids=[p.name for p in MANIFESTS])
    def manifest(self, request: pytest.FixtureRequest) -> dict:  # type: ignore[type-arg]
        path: pathlib.Path = request.param
        return yaml.safe_load(path.read_text())

    def test_is_valid_yaml(self, manifest: dict) -> None:  # type: ignore[type-arg]
        assert isinstance(manifest, dict)

    def test_has_chaos_mesh_api_version(self, manifest: dict) -> None:  # type: ignore[type-arg]
        api = manifest.get("apiVersion", "")
        assert api.startswith("chaos-mesh.org/"), f"Wrong apiVersion: {api}"

    def test_has_valid_kind(self, manifest: dict) -> None:  # type: ignore[type-arg]
        valid_kinds = {"PodChaos", "NetworkChaos", "StressChaos", "DNSChaos", "IOChaos"}
        assert manifest.get("kind") in valid_kinds

    def test_has_metadata(self, manifest: dict) -> None:  # type: ignore[type-arg]
        meta = manifest.get("metadata", {})
        assert "name" in meta, "Manifest missing metadata.name"
        assert "labels" in meta, "Manifest missing metadata.labels"
        assert meta["labels"].get("experiment") == "chaos"

    def test_duration_max_thirty_seconds(self, manifest: dict) -> None:  # type: ignore[type-arg]
        spec = manifest.get("spec", {})
        duration = spec.get("duration", "")
        if duration:
            seconds = int(duration.rstrip("s"))
            assert seconds <= 30, f"Duration {duration} exceeds 30s safety limit"

    def test_target_label_selector(self, manifest: dict) -> None:  # type: ignore[type-arg]
        spec = manifest.get("spec", {})
        selector = spec.get("selector", {})
        labels = selector.get("labelSelectors", {})
        assert labels.get("app") == "fastapi-template", "Must target fastapi-template pods"

    def test_pod_kill_mode_is_one(self, manifest: dict) -> None:  # type: ignore[type-arg]
        if manifest.get("kind") == "PodChaos":
            spec = manifest.get("spec", {})
            assert spec.get("mode") == "one", "Pod kill must target one pod at a time"

    def test_cpu_stress_has_load_limit(self, manifest: dict) -> None:  # type: ignore[type-arg]
        if manifest.get("kind") == "StressChaos":
            spec = manifest.get("spec", {})
            stressors = spec.get("stressors", {})
            cpu = stressors.get("cpu", {})
            load = cpu.get("load", 0)
            assert load <= 100, f"CPU load {load} exceeds 100%"

    def test_network_chaos_has_target(self, manifest: dict) -> None:  # type: ignore[type-arg]
        if manifest.get("kind") in {"NetworkChaos"}:
            spec = manifest.get("spec", {})
            assert "target" in spec, "NetworkChaos must specify a target"
            target = spec["target"]
            assert target.get("selector", {}).get("labelSelectors", {}).get("app")


class TestChaosPodKill:
    """Specific tests for pod-kill chaos."""

    def test_action_is_pod_kill(self) -> None:
        doc = _load("pod-kill.yaml")
        assert doc["spec"]["action"] == "pod-kill"

    def test_mode_is_one(self) -> None:
        doc = _load("pod-kill.yaml")
        assert doc["spec"]["mode"] == "one"


class TestChaosNetworkLatency:
    """Specific tests for network-latency chaos."""

    def test_action_is_delay(self) -> None:
        doc = _load("network-latency.yaml")
        assert doc["spec"]["action"] == "delay"

    def test_latency_value(self) -> None:
        doc = _load("network-latency.yaml")
        assert doc["spec"]["delay"]["latency"] == "200ms"


class TestChaosCpuStress:
    """Specific tests for cpu-stress chaos."""

    def test_is_stress_chaos(self) -> None:
        doc = _load("cpu-stress.yaml")
        assert doc["kind"] == "StressChaos"

    def test_has_cpu_workers(self) -> None:
        doc = _load("cpu-stress.yaml")
        assert doc["spec"]["stressors"]["cpu"]["workers"] >= 1


class TestChaosDnsError:
    """Specific tests for dns-error chaos."""

    def test_action_is_error(self) -> None:
        doc = _load("dns-error.yaml")
        assert doc["spec"]["action"] == "error"


class TestChaosHttpTimeout:
    """Specific tests for http-timeout chaos."""

    def test_action_is_loss(self) -> None:
        doc = _load("http-timeout.yaml")
        assert doc["spec"]["action"] == "loss"

    def test_loss_is_one_hundred_percent(self) -> None:
        doc = _load("http-timeout.yaml")
        assert doc["spec"]["loss"]["loss"] == "100"


class TestChaosDirectoryLayout:
    """Directory should be clean with only YAML files."""

    def test_no_non_yaml_files(self) -> None:
        non_yaml = [f for f in CHAOS_DIR.iterdir() if f.is_file() and f.suffix != ".yaml"]
        assert non_yaml == [], f"Non-YAML files in chaos dir: {non_yaml}"

    def test_all_files_parseable(self) -> None:
        for path in MANIFESTS:
            doc = yaml.safe_load(path.read_text())
            assert isinstance(doc, dict), f"{path.name} is not valid YAML"
