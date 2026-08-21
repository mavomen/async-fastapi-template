#!/usr/bin/env bash
#
# Run Chaos Mesh experiments against the app deployed in the current kubectl
# context and assert self-healing after each one.
#
# Usage:
#   ./scripts/run_chaos_experiments.sh [experiment ...]
#   # e.g.: ./scripts/run_chaos_experiments.sh pod-kill network-latency
#   # With no args, runs every manifest in $CHAOS_DIR (deps/ excluded).
#
# Environment:
#   NAMESPACE          target namespace (default: default)
#   APP_DEPLOYMENT     app Deployment name (default: fastapi-template)
#   CHAOS_DIR          directory containing experiment manifests (default: k8s/chaos)
#   RECOVERY_TIMEOUT   seconds to wait for rollout recovery (default: 180)
#   GITHUB_STEP_SUMMARY  when set, a PASS/FAIL table is appended
#
# Exit code: number of failed experiments (0 = all passed).

set -uo pipefail

NAMESPACE="${NAMESPACE:-default}"
APP_DEPLOYMENT="${APP_DEPLOYMENT:-fastapi-template}"
CHAOS_DIR="${CHAOS_DIR:-k8s/chaos}"
RECOVERY_TIMEOUT="${RECOVERY_TIMEOUT:-180}"
HEALTH_PATH="/healthz"
PROBE_IMAGE="curlimages/curl:8.9.1"
APP_SERVICE="http://${APP_DEPLOYMENT}.${NAMESPACE}.svc.cluster.local${HEALTH_PATH}"

APPLIED=()
FAILED=()
PASSED=()

cleanup() {
    for manifest in "${APPLIED[@]:-}"; do
        [ -n "$manifest" ] || continue
        kubectl delete -f "$manifest" --ignore-not-found --wait=false >/dev/null 2>&1
    done
}
trap cleanup EXIT

summary_header() {
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        {
            echo "| Experiment | Result |"
            echo "|------------|--------|"
        } >>"$GITHUB_STEP_SUMMARY"
    fi
}

summary_row() {
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        echo "| $1 | $2 |" >>"$GITHUB_STEP_SUMMARY"
    fi
}

duration_seconds() {
    # Parse the `duration:` field from an experiment manifest ("30s" -> 30).
    local dur
    dur=$(grep -E '^\s*duration:' "$1" | head -1 | grep -oE '[0-9]+')
    echo "${dur:-30}"
}

health_ok() {
    kubectl run "chaos-probe-$$-$1" --rm -i --restart=Never \
        --image="$PROBE_IMAGE" --quiet -- \
        curl -fsS -o /dev/null -m 10 "$APP_SERVICE" >/dev/null 2>&1
}

run_experiment() {
    local manifest="$1"
    local name
    name=$(basename "$manifest" .yaml)
    local duration
    duration=$(duration_seconds "$manifest")

    echo "::group::[chaos] $name (duration ${duration}s)"

    if ! kubectl apply -f "$manifest"; then
        echo "::error::[chaos] $name: failed to apply manifest"
        FAILED+=("$name")
        echo "::endgroup::"
        return
    fi
    APPLIED+=("$manifest")

    sleep "$duration"
    kubectl delete -f "$manifest" --ignore-not-found --wait=true >/dev/null 2>&1

    local ok=1
    if ! kubectl rollout status "deployment/${APP_DEPLOYMENT}" \
        --namespace "$NAMESPACE" --timeout="${RECOVERY_TIMEOUT}s"; then
        echo "::error::[chaos] $name: deployment did not recover within ${RECOVERY_TIMEOUT}s"
        ok=0
    fi

    if ! health_ok "$name"; then
        echo "::error::[chaos] $name: ${HEALTH_PATH} not healthy after recovery"
        ok=0
    fi

    if [ "$ok" -eq 1 ]; then
        echo "[chaos] $name: PASS"
        PASSED+=("$name")
    else
        FAILED+=("$name")
        kubectl describe pods --namespace "$NAMESPACE" | tail -50 || true
    fi

    echo "::endgroup::"
}

mapfile -t MANIFESTS < <(
    if [ "$#" -gt 0 ]; then
        for exp in "$@"; do echo "${CHAOS_DIR}/${exp}.yaml"; done
    else
        find "$CHAOS_DIR" -maxdepth 1 -name '*.yaml' ! -name 'values-*.yaml' | sort
    fi
)

if [ "${#MANIFESTS[@]}" -eq 0 ] || [ -z "${MANIFESTS[0]}" ]; then
    echo "::error::No experiment manifests found in ${CHAOS_DIR}"
    exit 1
fi

for manifest in "${MANIFESTS[@]}"; do
    if [ ! -f "$manifest" ]; then
        echo "::error::Experiment manifest not found: $manifest"
        FAILED+=("$(basename "$manifest" .yaml)")
        continue
    fi
    run_experiment "$manifest"
done

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    summary_header
    for name in "${PASSED[@]:-}"; do [ -n "$name" ] && summary_row "$name" "PASS"; done
    for name in "${FAILED[@]:-}"; do [ -n "$name" ] && summary_row "$name" "FAIL"; done
fi

echo "[chaos] completed: ${#PASSED[@]} passed, ${#FAILED[@]} failed"
exit "${#FAILED[@]}"
