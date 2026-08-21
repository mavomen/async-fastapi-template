"""Tests for Flagger canary deployment manifests and Helm templates."""

from __future__ import annotations

from pathlib import Path

import yaml

HELM_DIR = Path(__file__).resolve().parent.parent / "helm" / "async-fastapi-template"
K8S_DIR = Path(__file__).resolve().parent.parent / "k8s"


class TestHelmCanaryTemplate:
    """Validate the Flagger Canary Helm template renders correctly."""

    def _load_values(self) -> dict:
        with (HELM_DIR / "values.yaml").open() as fh:
            return yaml.safe_load(fh)  # type: ignore[no-any-return]

    def test_canary_disabled_by_default(self) -> None:
        values = self._load_values()
        assert values["canary"]["enabled"] is False

    def test_canary_values_have_analysis(self) -> None:
        values = self._load_values()
        analysis = values["canary"]["analysis"]
        assert "interval" in analysis
        assert "threshold" in analysis
        assert "maxWeight" in analysis
        assert "stepWeight" in analysis
        assert "metrics" in analysis

    def test_canary_metrics_defined(self) -> None:
        values = self._load_values()
        metrics = values["canary"]["analysis"]["metrics"]
        assert len(metrics) >= 2
        metric_names = [m["name"] for m in metrics]
        assert "request-success-rate" in metric_names
        assert "request-duration" in metric_names

    def test_canary_success_rate_threshold(self) -> None:
        values = self._load_values()
        metrics = values["canary"]["analysis"]["metrics"]
        sr = next(m for m in metrics if m["name"] == "request-success-rate")
        assert sr["thresholdRange"]["min"] >= 99

    def test_canary_duration_threshold(self) -> None:
        values = self._load_values()
        metrics = values["canary"]["analysis"]["metrics"]
        dur = next(m for m in metrics if m["name"] == "request-duration")
        assert dur["thresholdRange"]["max"] <= 1000

    def test_canary_template_file_exists(self) -> None:
        assert (HELM_DIR / "canary.yaml").exists()

    def test_canary_chart_version_bumped(self) -> None:
        with (HELM_DIR / "Chart.yaml").open() as fh:
            chart = yaml.safe_load(fh)  # type: ignore[no-any-return]
        assert chart["version"] == "0.3.0"

    def test_canary_chart_has_flagger_dependency(self) -> None:
        with (HELM_DIR / "Chart.yaml").open() as fh:
            chart = yaml.safe_load(fh)  # type: ignore[no-any-return]
        deps = chart.get("dependencies", [])
        assert any(d["name"] == "flagger" for d in deps)

    def test_flagger_dependency_condition(self) -> None:
        with (HELM_DIR / "Chart.yaml").open() as fh:
            chart = yaml.safe_load(fh)  # type: ignore[no-any-return]
        deps = chart.get("dependencies", [])
        flagger = next(d for d in deps if d["name"] == "flagger")
        assert flagger["condition"] == "canary.enabled"


class TestK8sCanaryManifest:
    """Validate the raw k8s canary manifest."""

    def _load_canary(self) -> dict:
        with (K8S_DIR / "canary.yaml").open() as fh:
            return yaml.safe_load(fh)  # type: ignore[no-any-return]

    def test_canary_exists(self) -> None:
        assert (K8S_DIR / "canary.yaml").exists()

    def test_kind_is_canary(self) -> None:
        doc = self._load_canary()
        assert doc["kind"] == "Canary"

    def test_api_version(self) -> None:
        doc = self._load_canary()
        assert doc["apiVersion"] == "flagger.app/v1beta1"

    def test_target_references_deployment(self) -> None:
        doc = self._load_canary()
        target = doc["spec"]["targetRef"]
        assert target["kind"] == "Deployment"
        assert target["name"] == "fastapi-template"

    def test_ingress_reference(self) -> None:
        doc = self._load_canary()
        ingress = doc["spec"]["ingressRef"]
        assert ingress["kind"] == "Ingress"
        assert ingress["name"] == "fastapi-template"

    def test_service_port_configured(self) -> None:
        doc = self._load_canary()
        svc = doc["spec"]["service"]
        assert svc["port"] == 80
        assert svc["targetPort"] == 8000

    def test_analysis_step_weight(self) -> None:
        doc = self._load_canary()
        analysis = doc["spec"]["analysis"]
        assert analysis["stepWeight"] == 10
        assert analysis["maxWeight"] == 50

    def test_analysis_threshold(self) -> None:
        doc = self._load_canary()
        analysis = doc["spec"]["analysis"]
        assert analysis["threshold"] == 5

    def test_analysis_metrics(self) -> None:
        doc = self._load_canary()
        metrics = doc["spec"]["analysis"]["metricsRef"]
        assert len(metrics) == 2
        names = [m["name"] for m in metrics]
        assert "request-success-rate" in names
        assert "request-duration" in names

    def test_analysis_iterations(self) -> None:
        doc = self._load_canary()
        assert doc["spec"]["analysis"]["iterations"] == 10


class TestDeploymentCanaryCompatibility:
    """Verify the existing Deployment is compatible with Flagger."""

    def _load_deployment(self) -> str:
        return (K8S_DIR / "deployment.yaml").read_text()

    def test_deployment_has_strategy(self) -> None:
        content = self._load_deployment()
        assert "RollingUpdate" in content

    def test_deployment_has_health_checks(self) -> None:
        content = self._load_deployment()
        assert "/healthz" in content
        assert "/readyz" in content

    def test_deployment_has_app_label(self) -> None:
        content = self._load_deployment()
        assert "app: fastapi-template" in content

    def test_helm_deployment_has_app_label(self) -> None:
        helm_deploy = (HELM_DIR / "deployment.yaml").read_text()
        assert "app: {{ .Release.Name }}" in helm_deploy


class TestHelmCanaryTemplateStructure:
    """Validate the canary.yaml template structure."""

    def _read_template(self) -> str:
        return (HELM_DIR / "canary.yaml").read_text()

    def test_template_is_conditional(self) -> None:
        content = self._read_template()
        assert "canary.enabled" in content or ".Values.canary.enabled" in content

    def test_template_references_release_name(self) -> None:
        content = self._read_template()
        assert ".Release.Name" in content

    def test_template_has_analysis(self) -> None:
        content = self._read_template()
        assert "analysis:" in content

    def test_template_has_metrics(self) -> None:
        content = self._read_template()
        assert "metricsRef" in content

    def test_template_has_progress_deadline(self) -> None:
        content = self._read_template()
        assert "progressDeadlineSeconds" in content
