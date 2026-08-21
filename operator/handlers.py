"""Kopf-based Kubernetes operator for FastAPIApp CRD.

Manages Deployment, Service, HPA, and PDB lifecycle for FastAPI applications
using a declarative CRD.
"""

from __future__ import annotations

import dataclasses

import kopf
import kubernetes
from kubernetes.client import (
    V1Container,
    V1ContainerPort,
    V1Deployment,
    V1DeploymentSpec,
    V1EnvVar,
    V1HorizontalPodAutoscaler,
    V1HorizontalPodAutoscalerSpec,
    V1HTTPGet,
    V1LabelSelector,
    V1PodDisruptionBudget,
    V1PodDisruptionBudgetSpec,
    V1PodSpec,
    V1PodTemplateSpec,
    V1Probe,
    V1ResourceRequirements,
    V1Service,
    V1ServicePort,
    V1ServiceSpec,
)

APP_LABEL = "app.kubernetes.io/managed-by"
APP_VALUE = "fastapi-operator"
COMPONENT_LABEL = "app.kubernetes.io/component"
TIMEOUT = 60


def _labels(name: str, namespace: str) -> dict[str, str]:
    """Return standard labels for child resources."""
    return {
        "app": name,
        APP_LABEL: APP_VALUE,
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/namespace": namespace,
    }


def _env_vars(spec: dict) -> list[V1EnvVar]:
    """Parse env array from CRD spec into V1EnvVar list."""
    return [V1EnvVar(name=e["name"], value=str(e["value"])) for e in (spec.get("env") or [])]


def _resources(spec: dict) -> V1ResourceRequirements | None:
    """Parse resource requirements from CRD spec."""
    res = spec.get("resources")
    if not res:
        return None
    return V1ResourceRequirements(
        requests=res.get("requests"),
        limits=res.get("limits"),
    )


def build_deployment(name: str, namespace: str, spec: dict) -> V1Deployment:
    """Build a Deployment from CRD spec."""
    labels = _labels(name, namespace)
    replicas = spec.get("replicas", 2)
    port = spec.get("port", 8000)
    image = spec["image"]

    container = V1Container(
        name="app",
        image=image,
        ports=[V1ContainerPort(container_port=port)],
        env=_env_vars(spec),
        resources=_resources(spec),
        readiness_probe=V1Probe(
            http_get=V1HTTPGet(path="/readyz", port=port),
            initial_delay_seconds=5,
            period_seconds=5,
        ),
        liveness_probe=V1Probe(
            http_get=V1HTTPGet(path="/healthz", port=port),
            initial_delay_seconds=10,
            period_seconds=10,
        ),
    )

    return V1Deployment(
        metadata={
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        spec=V1DeploymentSpec(
            replicas=replicas,
            selector=V1LabelSelector(match_labels={"app": name}),
            template=V1PodTemplateSpec(
                metadata={"labels": labels},
                spec=V1PodSpec(containers=[container]),
            ),
        ),
    )


def build_service(name: str, namespace: str, spec: dict) -> V1Service:
    """Build a Service from CRD spec."""
    labels = _labels(name, namespace)
    port = spec.get("port", 8000)

    return V1Service(
        metadata={
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        spec=V1ServiceSpec(
            selector={"app": name},
            ports=[V1ServicePort(port=port, target_port=port)],
            type="ClusterIP",
        ),
    )


def build_hpa(name: str, namespace: str, spec: dict) -> V1HorizontalPodAutoscaler | None:
    """Build an HPA if autoscaling is enabled."""
    scaling = spec.get("autoscaling", {})
    if not scaling.get("enabled"):
        return None

    return V1HorizontalPodAutoscaler(
        metadata={
            "name": name,
            "namespace": namespace,
            "labels": _labels(name, namespace),
        },
        spec=V1HorizontalPodAutoscalerSpec(
            min_replicas=scaling.get("minReplicas", 2),
            max_replicas=scaling.get("maxReplicas", 10),
            scale_target_ref={
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": name,
            },
            metrics=[
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "average_utilization": scaling.get(
                                "targetCPUUtilizationPercentage", 80
                            ),
                        },
                    },
                }
            ],
        ),
    )


def build_pdb(name: str, namespace: str, spec: dict) -> V1PodDisruptionBudget | None:
    """Build a PDB if pdb config is provided."""
    pdb_spec = spec.get("pdb")
    if not pdb_spec:
        return None

    return V1PodDisruptionBudget(
        metadata={
            "name": name,
            "namespace": namespace,
            "labels": _labels(name, namespace),
        },
        spec=V1PodDisruptionBudgetSpec(
            min_available=pdb_spec.get("minAvailable", 1),
            selector=V1LabelSelector(match_labels={"app": name}),
        ),
    )


# ──────────────────────────────────────────────────────
# Kopf handlers
# ──────────────────────────────────────────────────────

ApiException = kubernetes.client.exceptions.ApiException


@dataclasses.dataclass(frozen=True, slots=True)
class _ResourceOps:
    """Bundle the API client and its CRUD method names for a single resource type."""

    api: object
    read_fn: str
    create_fn: str
    patch_fn: str
    delete_fn: str
    label: str


def _create_or_patch(
    ops: _ResourceOps,
    name: str,
    namespace: str,
    desired: object,
    logger: kopf.types.Logger,
) -> None:
    """Create a resource if missing, patch if it exists."""
    try:
        getattr(ops.api, ops.read_fn)(name, namespace)
        getattr(ops.api, ops.patch_fn)(name, namespace, desired)
        logger.info("Patched %s %s/%s", ops.label, namespace, name)
    except ApiException as exc:
        if exc.status == 404:
            getattr(ops.api, ops.create_fn)(namespace, desired)
            logger.info("Created %s %s/%s", ops.label, namespace, name)
        else:
            raise


def _delete_if_exists(
    ops: _ResourceOps, name: str, namespace: str, logger: kopf.types.Logger
) -> None:
    """Delete a resource if it exists; ignore 404."""
    try:
        getattr(ops.api, ops.delete_fn)(name, namespace)
        logger.info("Deleted %s %s/%s", ops.label, namespace, name)
    except ApiException as exc:
        if exc.status != 404:
            raise


@kopf.on.create("fastapiapps")
@kopf.on.update("fastapiapps")
async def reconcile(
    spec: dict, name: str, namespace: str, logger: kopf.types.Logger, **_: object
) -> None:
    """Create or update child resources when FastAPIApp changes."""
    # Deployment
    deploy_ops = _ResourceOps(
        api=kubernetes.client.AppsV1Api(),
        read_fn="read_namespaced_deployment",
        create_fn="create_namespaced_deployment",
        patch_fn="patch_namespaced_deployment",
        delete_fn="delete_namespaced_deployment",
        label="deployment",
    )
    _create_or_patch(
        deploy_ops, name, namespace, kopf.adopt(build_deployment(name, namespace, spec)), logger
    )

    # Service
    svc_ops = _ResourceOps(
        api=kubernetes.client.CoreV1Api(),
        read_fn="read_namespaced_service",
        create_fn="create_namespaced_service",
        patch_fn="patch_namespaced_service",
        delete_fn="delete_namespaced_service",
        label="service",
    )
    _create_or_patch(
        svc_ops, name, namespace, kopf.adopt(build_service(name, namespace, spec)), logger
    )

    # HPA (optional)
    desired_hpa = build_hpa(name, namespace, spec)
    hpa_ops = _ResourceOps(
        api=kubernetes.client.AutoscalingV2Api(),
        read_fn="read_namespaced_horizontal_pod_autoscaler",
        create_fn="create_namespaced_horizontal_pod_autoscaler",
        patch_fn="patch_namespaced_horizontal_pod_autoscaler",
        delete_fn="delete_namespaced_horizontal_pod_autoscaler",
        label="HPA",
    )
    if desired_hpa:
        _create_or_patch(hpa_ops, name, namespace, kopf.adopt(desired_hpa), logger)
    else:
        _delete_if_exists(hpa_ops, name, namespace, logger)

    # PDB (optional)
    desired_pdb = build_pdb(name, namespace, spec)
    pdb_ops = _ResourceOps(
        api=kubernetes.client.PolicyV1Api(),
        read_fn="read_namespaced_pod_disruption_budget",
        create_fn="create_namespaced_pod_disruption_budget",
        patch_fn="patch_namespaced_pod_disruption_budget",
        delete_fn="delete_namespaced_pod_disruption_budget",
        label="PDB",
    )
    if desired_pdb:
        _create_or_patch(pdb_ops, name, namespace, kopf.adopt(desired_pdb), logger)
    else:
        _delete_if_exists(pdb_ops, name, namespace, logger)


@kopf.on.delete("fastapiapps")
async def on_delete(
    spec: dict, name: str, namespace: str, logger: kopf.types.Logger, **_: object
) -> None:
    """Log deletion — child resources are garbage-collected via ownerReferences."""
    logger.info(
        "FastAPIApp %s/%s deleted; child resources will be garbage-collected", namespace, name
    )
