"""Tests for K8s operator CRD, builders, and handler logic."""

from __future__ import annotations

import importlib
import pathlib
import sys
import types
from unittest.mock import MagicMock

import pytest
import yaml

OPERATOR_DIR = pathlib.Path("operator")
CRD_DIR = OPERATOR_DIR / "crds"

# ─── CRD validation ──────────────────────────────────


class TestCRDStructure:
    """CRD YAML is valid and has expected fields."""

    def _load_crd(self) -> dict:  # type: ignore[type-arg]
        return yaml.safe_load((CRD_DIR / "fastapiapp-crd.yaml").read_text())  # type: ignore[no-any-return]

    def test_crd_file_exists(self) -> None:
        assert (CRD_DIR / "fastapiapp-crd.yaml").exists()

    def test_crd_api_version(self) -> None:
        doc = self._load_crd()
        assert doc["apiVersion"] == "apiextensions.k8s.io/v1"

    def test_crd_kind(self) -> None:
        doc = self._load_crd()
        assert doc["kind"] == "CustomResourceDefinition"

    def test_crd_group(self) -> None:
        doc = self._load_crd()
        assert doc["spec"]["group"] == "app.example.com"

    def test_crd_kind_name(self) -> None:
        doc = self._load_crd()
        assert doc["spec"]["names"]["kind"] == "FastAPIApp"

    def test_crd_plural(self) -> None:
        doc = self._load_crd()
        assert doc["spec"]["names"]["plural"] == "fastapiapps"

    def test_crd_short_names(self) -> None:
        doc = self._load_crd()
        assert "fa" in doc["spec"]["names"]["shortNames"]

    def test_crd_has_v1_version(self) -> None:
        doc = self._load_crd()
        versions = doc["spec"]["versions"]
        assert any(v["name"] == "v1" for v in versions)

    def test_crd_has_status_subresource(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        assert v1.get("subresources", {}).get("status") == {}

    def test_crd_spec_requires_image(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        schema = v1["schema"]["openAPIV3Schema"]
        spec_props = schema["properties"]["spec"]
        assert "image" in spec_props["required"]

    def test_crd_has_replicas_field(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        spec_props = v1["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
        assert "replicas" in spec_props
        assert spec_props["replicas"]["type"] == "integer"

    def test_crd_has_autoscaling_field(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        spec_props = v1["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
        assert "autoscaling" in spec_props
        assert "enabled" in spec_props["autoscaling"]["properties"]

    def test_crd_has_pdb_field(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        spec_props = v1["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
        assert "pdb" in spec_props
        assert "minAvailable" in spec_props["pdb"]["properties"]

    def test_crd_has_printer_columns(self) -> None:
        doc = self._load_crd()
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        cols = v1.get("additionalPrinterColumns", [])
        names = [c["name"] for c in cols]
        assert "Image" in names
        assert "Replicas" in names
        assert "Phase" in names
        assert "Age" in names


class TestCRDFieldDefaults:
    """Verify default values in the CRD schema."""

    def _get_spec_prop(self, prop_name: str) -> dict:  # type: ignore[type-arg]
        doc = yaml.safe_load((CRD_DIR / "fastapiapp-crd.yaml").read_text())
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        return v1["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"][prop_name]  # type: ignore[no-any-return]

    def test_replicas_default_two(self) -> None:
        prop = self._get_spec_prop("replicas")
        assert prop["default"] == 2

    def test_replicas_minimum_zero(self) -> None:
        prop = self._get_spec_prop("replicas")
        assert prop["minimum"] == 0

    def test_port_default_8000(self) -> None:
        prop = self._get_spec_prop("port")
        assert prop["default"] == 8000

    def test_autoscaling_disabled_by_default(self) -> None:
        prop = self._get_spec_prop("autoscaling")
        assert prop["properties"]["enabled"]["default"] is False

    def test_autoscaling_max_replicas(self) -> None:
        prop = self._get_spec_prop("autoscaling")
        assert prop["properties"]["maxReplicas"]["default"] == 10

    def test_pdb_min_available_default(self) -> None:
        prop = self._get_spec_prop("pdb")
        assert prop["properties"]["minAvailable"]["default"] == 1


# ─── Builder tests ───────────────────────────────────

# Patch out kopf and kubernetes to test pure builder logic


@pytest.fixture(autouse=True)
def _patch_external_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent operator modules from importing kopf/k8s at import time."""
    for mod_name in list(sys.modules):
        if mod_name.startswith("operator"):
            del sys.modules[mod_name]


def _import_handlers() -> types.ModuleType:  # type: ignore[type-arg]
    """Import the handlers module with kopf/kubernetes stubbed."""
    stubs: dict[str, types.ModuleType] = {}
    for mod_name in ["kopf", "kubernetes", "kubernetes.client", "kubernetes.client.exceptions"]:
        stub = types.ModuleType(mod_name)
        stubs[mod_name] = stub
        sys.modules[mod_name] = stub

    # Wire up submodule attributes so `from kubernetes.client import ...` works
    stubs["kubernetes"].client = stubs["kubernetes.client"]
    stubs["kubernetes.client"].exceptions = stubs["kubernetes.client.exceptions"]

    # Simple stub class that stores all kwargs as attributes
    class _Stub:
        def __init__(self, **kwargs: object) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    # Add minimal kubernetes.client classes as stubs
    kclient = stubs["kubernetes.client"]
    for cls_name in [
        "V1Container",
        "V1ContainerPort",
        "V1Deployment",
        "V1DeploymentSpec",
        "V1EnvVar",
        "V1HorizontalPodAutoscaler",
        "V1HorizontalPodAutoscalerSpec",
        "V1LabelSelector",
        "V1PodDisruptionBudget",
        "V1PodDisruptionBudgetSpec",
        "V1PodSpec",
        "V1PodTemplateSpec",
        "V1Probe",
        "V1ResourceRequirements",
        "V1Service",
        "V1ServicePort",
        "V1ServiceSpec",
        "V1TCPSocket",
        "V1HTTPGet",
    ]:
        setattr(kclient, cls_name, _Stub)

    # Add ApiException stub
    exc_mod = stubs["kubernetes.client.exceptions"]

    class FakeApiException(Exception):
        def __init__(self, status: int = 0, reason: str = "") -> None:
            self.status = status
            self.reason = reason

    exc_mod.ApiException = FakeApiException

    # kopf stubs
    kopf = stubs["kopf"]
    kopf.on = MagicMock()
    kopf.adopt = lambda obj, **_kw: obj  # passthrough

    # Add Logger type stub
    types_mod = types.ModuleType("kopf.types")

    class _Logger:
        pass

    types_mod.Logger = _Logger  # type: ignore[attr-defined]
    sys.modules["kopf.types"] = types_mod
    kopf.types = types_mod  # type: ignore[attr-defined]

    # Now import handlers
    spec = importlib.util.spec_from_file_location(
        "operator.handlers", str(OPERATOR_DIR / "handlers.py")
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["operator.handlers"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def handlers() -> types.ModuleType:  # type: ignore[type-arg]
    return _import_handlers()


class TestBuildDeployment:
    def test_creates_deployment(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("my-app", "default", {"image": "nginx:latest"})
        assert dep is not None
        assert dep.metadata["name"] == "my-app"

    def test_sets_replicas(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("x", "ns", {"image": "img", "replicas": 5})
        assert dep.spec.replicas == 5

    def test_default_replicas(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("x", "ns", {"image": "img"})
        assert dep.spec.replicas == 2

    def test_sets_image(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("x", "ns", {"image": "python:3.12"})
        assert dep.spec.template.spec.containers[0].image == "python:3.12"

    def test_sets_port(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("x", "ns", {"image": "img", "port": 9000})
        assert dep.spec.template.spec.containers[0].ports[0].container_port == 9000

    def test_sets_labels(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment("x", "ns", {"image": "img"})
        assert dep.metadata["labels"][handlers.APP_LABEL] == handlers.APP_VALUE

    def test_sets_env_vars(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        dep = handlers.build_deployment(
            "x", "ns", {"image": "img", "env": [{"name": "FOO", "value": "bar"}]}
        )
        container = dep.spec.template.spec.containers[0]
        assert container.env[0].name == "FOO"
        assert container.env[0].value == "bar"


class TestBuildService:
    def test_creates_service(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        svc = handlers.build_service("my-app", "default", {})
        assert svc.metadata["name"] == "my-app"

    def test_sets_port(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        svc = handlers.build_service("x", "ns", {"port": 9000})
        assert svc.spec.ports[0].port == 9000

    def test_cluster_ip(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        svc = handlers.build_service("x", "ns", {})
        assert svc.spec.type == "ClusterIP"


class TestBuildHPA:
    def test_returns_none_when_disabled(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        assert handlers.build_hpa("x", "ns", {}) is None

    def test_returns_none_when_explicitly_disabled(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        assert handlers.build_hpa("x", "ns", {"autoscaling": {"enabled": False}}) is None

    def test_creates_hpa_when_enabled(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        hpa = handlers.build_hpa("x", "ns", {"autoscaling": {"enabled": True}})
        assert hpa is not None

    def test_sets_min_max_replicas(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        hpa = handlers.build_hpa(
            "x", "ns", {"autoscaling": {"enabled": True, "minReplicas": 3, "maxReplicas": 15}}
        )
        assert hpa.spec.min_replicas == 3
        assert hpa.spec.max_replicas == 15

    def test_cpu_target(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        hpa = handlers.build_hpa(
            "x", "ns", {"autoscaling": {"enabled": True, "targetCPUUtilizationPercentage": 70}}
        )
        metric = hpa.spec.metrics[0]
        assert metric["resource"]["target"]["average_utilization"] == 70


class TestBuildPDB:
    def test_returns_none_when_missing(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        assert handlers.build_pdb("x", "ns", {}) is None

    def test_creates_pdb_when_present(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        pdb = handlers.build_pdb("x", "ns", {"pdb": {"minAvailable": 2}})
        assert pdb is not None

    def test_sets_min_available(self, handlers: types.ModuleType) -> None:  # type: ignore[type-arg]
        pdb = handlers.build_pdb("x", "ns", {"pdb": {"minAvailable": 3}})
        assert pdb.spec.min_available == 3


class TestModuleFiles:
    """Operator module structure is complete."""

    def test_handlers_file_exists(self) -> None:
        assert (OPERATOR_DIR / "handlers.py").exists()

    def test_crd_directory_exists(self) -> None:
        assert CRD_DIR.exists()

    def test_requirements_file_exists(self) -> None:
        assert (OPERATOR_DIR / "requirements.txt").exists()

    def test_requirements_has_kopf(self) -> None:
        content = (OPERATOR_DIR / "requirements.txt").read_text()
        assert "kopf" in content

    def test_requirements_has_kubernetes(self) -> None:
        content = (OPERATOR_DIR / "requirements.txt").read_text()
        assert "kubernetes" in content


# ─── Handler registration ────────────────────────────


class TestHandlerRegistration:
    """Handlers register against the explicit CRD group/version/plural."""

    @staticmethod
    def _source() -> str:
        return (OPERATOR_DIR / "handlers.py").read_text()

    def test_explicit_group_used(self) -> None:
        assert '"app.example.com", "v1", "fastapiapps"' in self._source()

    def test_no_single_arg_registration(self) -> None:
        source = self._source()
        for decorator in ["@kopf.on.create(", "@kopf.on.update(", "@kopf.on.delete("]:
            start = source.index(decorator)
            line = source[start : source.index("\n", start)]
            args = line[len(decorator) :].rstrip(")")
            assert args.count(",") >= 2, f"{decorator} must pass group+version+plural, got {args}"

    def test_resume_handler_registered(self) -> None:
        source = self._source()
        assert "@kopf.on.resume" in source
        # resume must be stacked on the same function as create/update
        resume_idx = source.index("@kopf.on.resume")
        reconcile_idx = source.index("async def reconcile")
        between = source[resume_idx:reconcile_idx]
        assert "@kopf.on.create" in between
        assert "@kopf.on.update" in between

    def test_delete_handler_registered(self) -> None:
        source = self._source()
        assert '@kopf.on.delete("app.example.com", "v1", "fastapiapps")' in source


# ─── RBAC manifest ───────────────────────────────────

RBAC_PATH = OPERATOR_DIR / "rbac.yaml"
DEPLOYMENT_PATH = OPERATOR_DIR / "deployment.yaml"
DOCKERFILE_PATH = OPERATOR_DIR / "Dockerfile"
EXAMPLE_CR_PATH = OPERATOR_DIR / "examples" / "fastapiapp-sample.yaml"


def _load_docs(path: pathlib.Path) -> list[dict]:  # type: ignore[type-arg]
    docs = list(yaml.safe_load_all(path.read_text()))
    return [d for d in docs if d is not None]


class TestOperatorRBAC:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.docs = _load_docs(RBAC_PATH)

    def _by_kind(self, kind: str) -> dict:  # type: ignore[type-arg]
        return next(d for d in self.docs if d["kind"] == kind)

    def test_service_account_exists(self) -> None:
        sa = self._by_kind("ServiceAccount")
        assert sa["metadata"]["name"] == "fastapi-operator"

    def test_service_account_automounts_token(self) -> None:
        sa = self._by_kind("ServiceAccount")
        assert sa["automountServiceAccountToken"] is True

    def test_cluster_role_covers_all_managed_resources(self) -> None:
        role = self._by_kind("ClusterRole")
        covered: dict[str, set[str]] = {}
        for rule in role["rules"]:
            for group in rule["apiGroups"]:
                for resource in rule["resources"]:
                    covered[f"{group}/{resource}"] = set(rule["verbs"])
        for expected in [
            "app.example.com/fastapiapps",
            "apps/deployments",
            "/services",
            "/events",
            "autoscaling/horizontalpodautoscalers",
            "policy/poddisruptionbudgets",
        ]:
            assert expected in covered, f"missing RBAC rule for {expected}"

    def test_full_lifecycle_verbs_on_children(self) -> None:
        role = self._by_kind("ClusterRole")
        verbs_by_resource: dict[str, set[str]] = {}
        for rule in role["rules"]:
            for resource in rule["resources"]:
                if resource != "events":
                    verbs_by_resource[resource] = set(rule["verbs"])
        required = {"get", "list", "watch", "create", "update", "patch", "delete"}
        for resource, verbs in verbs_by_resource.items():
            assert required <= verbs, f"{resource} missing verbs: {required - verbs}"

    def test_events_minimal_verbs(self) -> None:
        role = self._by_kind("ClusterRole")
        events_rule = next(r for r in role["rules"] if "events" in r.get("resources", []))
        assert set(events_rule["verbs"]) == {"create", "patch"}

    def test_binding_links_role_and_sa(self) -> None:
        binding = self._by_kind("ClusterRoleBinding")
        assert binding["roleRef"]["name"] == "fastapi-operator"
        subject = binding["subjects"][0]
        assert subject["kind"] == "ServiceAccount"
        assert subject["name"] == "fastapi-operator"


class TestOperatorDeployment:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        docs = _load_docs(DEPLOYMENT_PATH)
        self.deployment = docs[0]
        self.pod_spec = self.deployment["spec"]["template"]["spec"]
        self.container = self.pod_spec["containers"][0]

    def test_uses_operator_service_account(self) -> None:
        assert self.pod_spec["serviceAccountName"] == "fastapi-operator"

    def test_pod_security_context(self) -> None:
        psc = self.pod_spec["securityContext"]
        assert psc["runAsNonRoot"] is True
        assert psc["runAsUser"] == 1000
        assert psc["seccompProfile"]["type"] == "RuntimeDefault"

    def test_container_security_context(self) -> None:
        csc = self.container["securityContext"]
        assert csc["allowPrivilegeEscalation"] is False
        assert csc["readOnlyRootFilesystem"] is True
        assert csc["runAsNonRoot"] is True
        assert csc["capabilities"]["drop"] == ["ALL"]

    def test_runs_kopf_with_liveness(self) -> None:
        assert self.container["command"][:2] == ["kopf", "run"]
        assert "--all-namespaces" in self.container["args"]
        assert any(a.startswith("--liveness=http://") for a in self.container["args"])

    def test_liveness_probe(self) -> None:
        probe = self.container["livenessProbe"]
        assert probe["httpGet"]["path"] == "/healthz"
        assert probe["httpGet"]["port"] == "liveness"

    def test_tmp_empty_dir_mounted(self) -> None:
        volumes = self.pod_spec["volumes"]
        vol_names = [v["name"] for v in volumes]
        assert "tmp" in vol_names
        tmp_vol = next(v for v in volumes if v["name"] == "tmp")
        assert "emptyDir" in tmp_vol
        mount_paths = [m["mountPath"] for m in self.container["volumeMounts"]]
        assert "/tmp" in mount_paths

    def test_resources_bounded(self) -> None:
        resources = self.container["resources"]
        assert "requests" in resources
        assert "limits" in resources


class TestOperatorDockerfile:
    def test_dockerfile_exists(self) -> None:
        assert DOCKERFILE_PATH.exists()

    def test_slim_base_image(self) -> None:
        content = DOCKERFILE_PATH.read_text()
        assert "FROM python:3.12-slim" in content

    def test_runs_as_non_root(self) -> None:
        content = DOCKERFILE_PATH.read_text()
        assert "USER 1000:1000" in content

    def test_has_healthcheck(self) -> None:
        content = DOCKERFILE_PATH.read_text()
        assert "HEALTHCHECK" in content
        assert "27020/healthz" in content

    def test_installs_pinned_requirements(self) -> None:
        content = DOCKERFILE_PATH.read_text()
        assert "COPY requirements.txt" in content
        assert "pip install --no-cache-dir -r requirements.txt" in content


class TestExampleCR:
    def _load_cr(self) -> dict:  # type: ignore[type-arg]
        return yaml.safe_load(EXAMPLE_CR_PATH.read_text())  # type: ignore[no-any-return]

    def test_example_file_exists(self) -> None:
        assert EXAMPLE_CR_PATH.exists()

    def test_api_version_matches_crd(self) -> None:
        cr = self._load_cr()
        assert cr["apiVersion"] == "app.example.com/v1"

    def test_kind_matches_crd(self) -> None:
        cr = self._load_cr()
        assert cr["kind"] == "FastAPIApp"

    def test_required_image_field_present(self) -> None:
        cr = self._load_cr()
        assert isinstance(cr["spec"]["image"], str)
        assert cr["spec"]["image"]

    def test_exercises_optional_fields(self) -> None:
        spec = self._load_cr()["spec"]
        assert isinstance(spec["replicas"], int)
        assert spec["autoscaling"]["enabled"] is True
        assert "minAvailable" in spec["pdb"]

    def test_conforms_to_crd_schema_properties(self) -> None:
        cr = self._load_cr()
        doc = yaml.safe_load((CRD_DIR / "fastapiapp-crd.yaml").read_text())
        v1 = next(v for v in doc["spec"]["versions"] if v["name"] == "v1")
        allowed = set(v1["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"])
        unknown = set(cr["spec"]) - allowed
        assert not unknown, f"example uses fields absent from CRD schema: {unknown}"
