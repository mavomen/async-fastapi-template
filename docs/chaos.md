# Chaos Engineering

The template ships a weekly chaos-engineering pipeline that injects real faults
into a disposable Kubernetes cluster and asserts the application self-heals.
This validates probe configuration, rollout recovery, and graceful degradation
under partial failure — before production finds out for you.

## What runs

A scheduled GitHub Actions workflow (`.github/workflows/chaos-engineering.yml`)
executes every Sunday at 04:00 UTC:

1. **Ephemeral kind cluster** is created (`helm/kind-action`).
2. **App image** is built from `Dockerfile.prod` and loaded into the cluster —
   the same artifact that ships to production gets fault-injected.
3. **Dependencies**: pinned `postgres:16-alpine` / `redis:7-alpine` are deployed
   from `k8s/chaos/deps/`, with Service names matching the Helm chart defaults
   (`postgres:5432`, `redis:6379`).
4. **App stack**: the repo's own Helm chart installs as release
   `fastapi-template` with overrides from `k8s/chaos/values-chaos.yaml`
   (ingress off, autoscaling off, throwaway credentials). The release name gives
   pods the `app: fastapi-template` label that experiment selectors expect.
5. **Migrations** run via a one-off Job using the app image; `/healthz` must
   answer 200 *before* any fault is injected.
6. **Chaos Mesh** (pinned chart version) is installed with its DNS server
   component enabled, and the target namespace is labelled for injection.
7. **Experiments** run sequentially via `scripts/run_chaos_experiments.sh`.

## Experiments

All manifests live in `k8s/chaos/`, are 30 seconds long, and target
`app: fastapi-template` in the `default` namespace:

| Manifest | Kind | Fault |
|----------|------|-------|
| `pod-kill.yaml` | PodChaos | Kills one app pod |
| `cpu-stress.yaml` | StressChaos | CPU stress on all app pods |
| `network-latency.yaml` | NetworkChaos | Injected latency |
| `http-timeout.yaml` | NetworkChaos | Packet loss |
| `dns-error.yaml` | DNSChaos | DNS resolution failures |

## Recovery assertions

For each experiment the runner:

1. Applies the manifest and waits out the injection duration.
2. Deletes the experiment.
3. Requires `kubectl rollout status` to succeed within 180 seconds.
4. Requires `/healthz` to return 200 through an in-cluster probe.

Any failure fails the job. A PASS/FAIL table is written to the GitHub step
summary; pod descriptions and cluster events are uploaded as diagnostics
artifacts when anything fails.

Applied experiments are always cleaned up (`trap cleanup EXIT` +
`--ignore-not-found`), so a failed run never leaves faults behind.

## Running manually

Trigger any subset from the Actions tab (**Run workflow**) or with `gh`:

```bash
gh workflow run chaos-engineering.yml -f experiments=pod-kill,network-latency
gh workflow run chaos-engineering.yml -f experiments=all
```

To reproduce locally against your own kind cluster:

```bash
kind create cluster --name chaos-lab
docker build -f Dockerfile.prod -t async-fastapi-template:chaos .
kind load docker-image async-fastapi-template:chaos --name chaos-lab
kubectl apply -f k8s/chaos/deps/
helm install fastapi-template ./helm/async-fastapi-template \
  -f k8s/chaos/values-chaos.yaml --wait
# ... install Chaos Mesh as in the workflow, then:
./scripts/run_chaos_experiments.sh
```

## Adding an experiment

1. Add a manifest in `k8s/chaos/` following the existing pattern:
   30-second duration, `experiment: chaos` + `type: <name>` labels,
   selector on `app: fastapi-template`.
2. Nothing else needs updating — the workflow discovers top-level manifests
   automatically (`deps/` is excluded), and tests enforce the safety bounds
   via `tests/test_chaos_ci.py`.

## Safety notes

- Experiments only ever target the disposable CI cluster — never staging or
  production.
- Durations are capped at 120 seconds by test assertion.
- The job holds a `concurrency` lock so two runs can never interleave.
