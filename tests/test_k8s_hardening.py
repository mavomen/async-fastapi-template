"""Tests for Kubernetes hardening: securityContext, service account, network policy, ingress.

Validates that all K8s manifests and Helm templates enforce security best practices:
- Pod/container securityContext (runAsNonRoot, readOnlyRootFilesystem, drop ALL caps, seccomp)
- Dedicated ServiceAccount with automountServiceAccountToken: false
- NetworkPolicy ingress restricted to ingress-nginx namespace
- Ingress uses ingressClassName: nginx
- Cosign signing in CI

Run with:  poetry run pytest tests/test_k8s_hardening.py
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

K8S_DIR = pathlib.Path("k8s")
HELM_DIR = pathlib.Path("helm/async-fastapi-template")


def _load_yaml(path: pathlib.Path) -> list[dict]:
    with path.open() as f:
        docs = list(yaml.safe_load_all(f))
    return [d for d in docs if d is not None]


class TestK8sDeploymentHardening:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        docs = _load_yaml(K8S_DIR / "deployment.yaml")
        self.deployment = docs[0]

    def test_service_account_set(self) -> None:
        sa = self.deployment["spec"]["template"]["spec"].get("serviceAccountName")
        assert sa == "fastapi-template"

    def test_automount_disabled(self) -> None:
        assert (
            self.deployment["spec"]["template"]["spec"].get("automountServiceAccountToken") is False
        )

    def test_pod_security_context(self) -> None:
        psc = self.deployment["spec"]["template"]["spec"]["securityContext"]
        assert psc["runAsNonRoot"] is True
        assert psc["runAsUser"] == 1000
        assert psc["seccompProfile"]["type"] == "RuntimeDefault"

    def test_container_security_context(self) -> None:
        csc = self.deployment["spec"]["template"]["spec"]["containers"][0]["securityContext"]
        assert csc["allowPrivilegeEscalation"] is False
        assert csc["readOnlyRootFilesystem"] is True
        assert csc["runAsNonRoot"] is True
        assert csc["capabilities"]["drop"] == ["ALL"]

    def test_empty_dir_volumes(self) -> None:
        volumes = self.deployment["spec"]["template"]["spec"]["volumes"]
        vol_names = [v["name"] for v in volumes]
        assert "tmp" in vol_names
        assert "uploads" in vol_names
        for v in volumes:
            assert "emptyDir" in v

    def test_volume_mounts(self) -> None:
        mounts = self.deployment["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
        mount_paths = [m["mountPath"] for m in mounts]
        assert "/tmp" in mount_paths
        assert "/data/uploads" in mount_paths


class TestK8sServiceAccount:
    def test_service_account_exists(self) -> None:
        docs = _load_yaml(K8S_DIR / "service-account.yaml")
        sa = docs[0]
        assert sa["kind"] == "ServiceAccount"
        assert sa["metadata"]["name"] == "fastapi-template"
        assert sa["automountServiceAccountToken"] is False


class TestK8sNetworkPolicy:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        docs = _load_yaml(K8S_DIR / "network-policy.yaml")
        self.netpol = docs[0]

    def test_ingress_restricted_to_ingress_nginx(self) -> None:
        ingress_rules = self.netpol["spec"]["ingress"]
        for rule in ingress_rules:
            for from_rule in rule["from"]:
                ns_selector = from_rule.get("namespaceSelector", {})
                match = ns_selector.get("matchLabels", {})
                assert match.get("kubernetes.io/metadata.name") == "ingress-nginx", (
                    "Ingress should only allow traffic from ingress-nginx namespace"
                )

    def test_egress_allows_dns(self) -> None:
        egress = self.netpol["spec"]["egress"]
        dns_egress = [e for e in egress if any(p.get("port") == 53 for p in e.get("ports", []))]
        assert len(dns_egress) > 0, "DNS egress rule not found"

    def test_egress_allows_postgres_and_redis(self) -> None:
        egress = self.netpol["spec"]["egress"]
        db_egress = [
            e for e in egress if any(p.get("port") in (5432, 6379) for p in e.get("ports", []))
        ]
        assert len(db_egress) > 0, "Database/Redis egress rule not found"


class TestK8sIngress:
    def test_ingress_class_name(self) -> None:
        docs = _load_yaml(K8S_DIR / "ingress.yaml")
        ingress = docs[0]
        assert ingress["spec"]["ingressClassName"] == "nginx"

    def test_tls_configured(self) -> None:
        docs = _load_yaml(K8S_DIR / "ingress.yaml")
        ingress = docs[0]
        assert "tls" in ingress["spec"]


class TestHelmDeploymentHardening:
    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        content = (HELM_DIR / "deployment.yaml").read_text()
        assert "securityContext" in content
        self.content = content

    def test_pod_security_context_present(self) -> None:
        assert "runAsNonRoot" in self.content
        assert "seccompProfile" in self.content
        assert "RuntimeDefault" in self.content

    def test_container_security_context_present(self) -> None:
        assert "allowPrivilegeEscalation" in self.content
        assert "readOnlyRootFilesystem" in self.content
        assert "drop:" in self.content
        assert "ALL" in self.content

    def test_service_account_template(self) -> None:
        assert "serviceAccountName" in self.content
        assert "automountServiceAccountToken" in self.content

    def test_empty_dir_volumes(self) -> None:
        assert "emptyDir" in self.content


class TestHelmServiceAccount:
    def test_service_account_template_exists(self) -> None:
        path = HELM_DIR / "service-account.yaml"
        assert path.exists()
        content = path.read_text()
        assert "ServiceAccount" in content
        assert "automountServiceAccountToken: false" in content


class TestHelmIngressHardening:
    def test_ingress_class_name(self) -> None:
        content = (HELM_DIR / "service.yaml").read_text()
        assert "ingressClassName: nginx" in content


class TestHelmValues:
    def test_security_context_values(self) -> None:
        content = (HELM_DIR / "values.yaml").read_text()
        assert "podSecurityContext" in content
        assert "containerSecurityContext" in content
        assert "readOnlyRootFilesystem" in content


class TestCosignSigning:
    def test_cosign_in_docker_build(self) -> None:
        content = (pathlib.Path(".github/workflows/docker-build.yml")).read_text()
        assert "cosign" in content
        assert "id-token: write" in content

    def test_image_scan_workflow_exists(self) -> None:
        path = pathlib.Path(".github/workflows/image-scan.yml")
        assert path.exists()
        content = path.read_text()
        assert "trivy" in content.lower()
        assert "image-ref" in content
