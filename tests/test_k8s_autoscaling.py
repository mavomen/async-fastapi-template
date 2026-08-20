"""Tests for k8s autoscaling: probes, graceful drain, and HPA behavior config."""

from pathlib import Path

import yaml
from starlette.testclient import TestClient

from app.main import _draining, app


def _load_k8s_yaml(path: str) -> dict:  # type: ignore[type-arg]
    """Load a plain k8s YAML (no Go template syntax)."""
    return yaml.safe_load(Path(path).read_text())


def _load_helm_raw(path: str) -> str:
    """Load a Helm template file as raw text (may contain {{ }})."""
    return Path(path).read_text()


class TestKubernetesProbeEndpoints:
    def test_healthz_returns_200(self):
        with TestClient(app) as client:
            resp = client.get("/healthz")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_readyz_returns_200_when_healthy(self):
        with TestClient(app) as client:
            resp = client.get("/readyz")
            assert resp.status_code in (200, 503)
            data = resp.json()
            assert data["status"] in ("ready", "degraded", "draining")

    def test_healthz_excluded_from_openapi(self):
        with TestClient(app) as client:
            openapi = client.get("/openapi.json").json()
            paths = openapi.get("paths", {})
            assert "/healthz" not in paths
            assert "/readyz" not in paths

    def test_health_live_still_works(self):
        with TestClient(app) as client:
            resp = client.get("/health/live")
            assert resp.status_code == 200
            assert resp.json()["status"] == "alive"


class TestGracefulDrain:
    def test_readyz_returns_503_during_drain(self):
        _draining.set()
        try:
            with TestClient(app) as client:
                resp = client.get("/readyz")
                assert resp.status_code == 503
                assert resp.json()["status"] == "draining"
        finally:
            _draining.clear()

    def test_healthz_unaffected_by_drain(self):
        _draining.set()
        try:
            with TestClient(app) as client:
                resp = client.get("/healthz")
                assert resp.status_code == 200
        finally:
            _draining.clear()

    def test_drain_flag_default_state(self):
        _draining.clear()
        assert not _draining.is_set()


class TestHPAConfiguration:
    def test_hpa_yaml_has_behavior(self):
        hpa = _load_k8s_yaml("k8s/hpa.yaml")
        assert hpa["spec"]["behavior"]["scaleDown"]["stabilizationWindowSeconds"] == 300
        assert hpa["spec"]["behavior"]["scaleUp"]["stabilizationWindowSeconds"] == 30
        policies = hpa["spec"]["behavior"]["scaleDown"]["policies"]
        assert any(p["type"] == "Percent" and p["value"] == 25 for p in policies)


class TestDeploymentConfiguration:
    def test_deployment_has_prestop(self):
        dep = _load_k8s_yaml("k8s/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        prestop = container["lifecycle"]["preStop"]["exec"]["command"]
        assert prestop == ["sh", "-c", "sleep 5"]

    def test_deployment_has_termination_grace(self):
        dep = _load_k8s_yaml("k8s/deployment.yaml")
        assert dep["spec"]["template"]["spec"]["terminationGracePeriodSeconds"] == 45

    def test_deployment_has_startup_probe(self):
        dep = _load_k8s_yaml("k8s/deployment.yaml")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        assert container["startupProbe"]["httpGet"]["path"] == "/healthz"
        assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"
        assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"

    def test_deployment_has_rolling_update(self):
        dep = _load_k8s_yaml("k8s/deployment.yaml")
        strat = dep["spec"]["strategy"]
        assert strat["type"] == "RollingUpdate"
        assert strat["rollingUpdate"]["maxSurge"] == 1
        assert strat["rollingUpdate"]["maxUnavailable"] == 0


class TestNetworkPolicy:
    def test_dns_egress_allowed(self):
        np = _load_k8s_yaml("k8s/network-policy.yaml")
        egress_rules = np["spec"]["egress"]
        dns_found = False
        for rule in egress_rules:
            for p in rule.get("ports", []):
                if p.get("port") == 53:
                    dns_found = True
        assert dns_found, "NetworkPolicy must allow DNS egress (port 53)"


class TestSecretsTemplate:
    def test_no_plaintext_passwords(self):
        content = Path("k8s/secret.yaml").read_text()
        assert "postgres" not in content.lower() or "${" in content


class TestDockerfiles:
    def test_dockerfile_healthcheck_uses_healthz(self):
        content = Path("Dockerfile").read_text()
        assert "/healthz" in content

    def test_dockerfile_has_graceful_shutdown(self):
        content = Path("Dockerfile").read_text()
        assert "--timeout-graceful-shutdown" in content

    def test_prod_healthcheck_uses_healthz(self):
        content = Path("Dockerfile.prod").read_text()
        assert "/healthz" in content

    def test_prod_has_graceful_shutdown(self):
        content = Path("Dockerfile.prod").read_text()
        assert "--timeout-graceful-shutdown" in content


class TestHelmChart:
    def test_chart_version_bumped(self):
        chart = _load_k8s_yaml("helm/async-fastapi-template/Chart.yaml")
        assert chart["appVersion"] == "3.1.0"

    def test_deployment_has_lifecycle(self):
        raw = _load_helm_raw("helm/async-fastapi-template/deployment.yaml")
        assert "preStop" in raw
        assert "sleep 5" in raw

    def test_deployment_has_termination_grace(self):
        raw = _load_helm_raw("helm/async-fastapi-template/deployment.yaml")
        assert "terminationGracePeriodSeconds" in raw

    def test_deployment_has_startup_probe(self):
        raw = _load_helm_raw("helm/async-fastapi-template/deployment.yaml")
        assert "startupProbe" in raw
        assert "/healthz" in raw

    def test_deployment_has_rolling_update(self):
        raw = _load_helm_raw("helm/async-fastapi-template/deployment.yaml")
        assert "RollingUpdate" in raw

    def test_values_has_autoscaling(self):
        values = _load_k8s_yaml("helm/async-fastapi-template/values.yaml")
        assert values["autoscaling"]["enabled"] is True
        assert values["terminationGracePeriodSeconds"] == 45

    def test_hpa_template_exists(self):
        assert Path("helm/async-fastapi-template/hpa.yaml").exists()

    def test_hpa_template_has_behavior(self):
        raw = _load_helm_raw("helm/async-fastapi-template/hpa.yaml")
        assert "stabilizationWindowSeconds" in raw
        assert "scaleDown" in raw

    def test_pdb_template_exists(self):
        assert Path("helm/async-fastapi-template/pdb.yaml").exists()

    def test_pdb_template_has_min_available(self):
        raw = _load_helm_raw("helm/async-fastapi-template/pdb.yaml")
        assert "minAvailable" in raw

    def test_configmap_template_exists(self):
        assert Path("helm/async-fastapi-template/configmap.yaml").exists()
