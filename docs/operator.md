# Kubernetes Operator

The template ships a [Kopf](https://kopf.readthedocs.io/)-based operator that manages the
lifecycle of FastAPI application deployments through a declarative custom resource.
Instead of hand-writing Deployment/Service/HPA/PDB manifests, you declare a single
`FastAPIApp` object and the operator reconciles the child resources for you.

## What it manages

For every `FastAPIApp` custom resource, the operator creates and keeps in sync:

| Resource | Source field | Notes |
|----------|--------------|-------|
| `Deployment` | `image`, `replicas`, `port`, `env`, `resources` | Probes wired to `/readyz` and `/healthz` |
| `Service` | `port` | ClusterIP |
| `HorizontalPodAutoscaler` | `autoscaling.enabled` | Deleted when autoscaling is disabled |
| `PodDisruptionBudget` | `pdb` | Deleted when absent |

Child resources carry kopf owner references, so deleting the `FastAPIApp`
garbage-collects everything it created.

## Repository layout

```
operator/
├── crds/fastapiapp-crd.yaml   # CustomResourceDefinition (group: app.example.com)
├── handlers.py                # Kopf reconcile/delete handlers + resource builders
├── rbac.yaml                  # ServiceAccount, ClusterRole, ClusterRoleBinding
├── deployment.yaml            # Hardened in-cluster operator Deployment
├── Dockerfile                 # python:3.12-slim, non-root, HEALTHCHECK
├── requirements.txt           # kopf + kubernetes client pins
└── examples/fastapiapp-sample.yaml
```

## Installation

Apply in this order (RBAC before the operator pod starts):

```bash
kubectl create namespace fastapi-operator-system
kubectl apply -f operator/crds/fastapiapp-crd.yaml
kubectl apply -f operator/rbac.yaml
kubectl apply -f operator/deployment.yaml
```

The operator image is published by CI as
`ghcr.io/mavomen/async-fastapi-template/fastapi-operator` and is cosign-signed;
Trivy scans it on every build.

## Usage

```bash
kubectl apply -f operator/examples/fastapiapp-sample.yaml
kubectl get fastapiapps          # or: kubectl get fa
```

Example spec:

```yaml
apiVersion: app.example.com/v1
kind: FastAPIApp
metadata:
  name: demo-app
spec:
  image: ghcr.io/mavomen/async-fastapi-template:latest
  replicas: 2
  port: 8000
  env:
    - name: ENVIRONMENT
      value: production
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 80
  pdb:
    minAvailable: 1
```

## Behaviour notes

- **Reconciliation** runs on create, update, *and* resume — after an operator
  restart, existing `FastAPIApp` objects are re-reconciled without requiring an edit.
- **Explicit API group**: handlers register against `app.example.com/v1` rather than
  the bare plural name, so kopf does not scan every API group in the cluster.
- **Idempotency**: existing children are patched, missing children are created,
  disabled features (HPA/PDB) are removed — safe to run repeatedly.
- **Hardening**: the operator pod runs as non-root with a read-only root filesystem,
  dropped capabilities, seccomp `RuntimeDefault`, and liveness probing via kopf's
  built-in health server (`:27020/healthz`). Unlike the app's ServiceAccount, the
  operator SA mounts its token because it needs Kubernetes API access.

## Local development

```bash
cd operator
python -m venv .venv && .venv/bin/pip install -r requirements.txt
kind create cluster && kubectl apply -f crds/fastapiapp-crd.yaml
.venv/bin/kopf run handlers.py          # foreground, watches current kubeconfig context
```

Tests live in `tests/test_k8s_operator.py` and stub kopf/kubernetes, so they run
without a cluster:

```bash
poetry run pytest tests/test_k8s_operator.py
```
