#!/usr/bin/env bash
# Phase 0 capture harness: run the identical spike and record, into benchmarks/:
#   - <label>_replicas.csv : victim-app replica count over time
#   - k6: <label>_load.json (p95/p99 + error rate) ; locust: <label>_load_stats.csv
#
# Usage: ./capture.sh <label> <k6|locust> [target_url]
#   e.g. ./capture.sh reactive   k6             # reactive HPA only (baseline)
#        ./capture.sh predictive k6             # Sentinel agent running too
#
# Prereqs: kubectl pointed at the cluster; k6 or locust installed; a route to
# victim-app, e.g.  kubectl port-forward svc/victim-app 8080:80
set -euo pipefail

LABEL="${1:?usage: capture.sh <label> <k6|locust> [target_url]}"
TOOL="${2:?usage: capture.sh <label> <k6|locust> [target_url]}"
TARGET="${3:-http://localhost:8080}"
DEPLOY="${DEPLOY:-victim-app}"
NS="${NS:-default}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(cd "$HERE/.." && pwd)/benchmarks"
mkdir -p "$OUT"

REPLICAS_CSV="$OUT/${LABEL}_replicas.csv"
LOAD_JSON="$OUT/${LABEL}_load.json"

# 1. Record the replica count every 2s in the background (the "timeline").
echo "timestamp,replicas" > "$REPLICAS_CSV"
record_replicas() {
  while true; do
    n=$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.status.replicas}' 2>/dev/null || true)
    echo "$(date +%s),${n:-0}" >> "$REPLICAS_CSV"
    sleep 2
  done
}
record_replicas & REC_PID=$!
trap 'kill "$REC_PID" 2>/dev/null || true' EXIT

# 2. Run the identical spike.
case "$TOOL" in
  k6)
    # k6 exits 99 when a threshold is breached -- that's a valid result under
    # load, not a capture failure, so don't let it abort the script.
    set +e
    K6_SUMMARY_OUT="$LOAD_JSON" k6 run -e TARGET="$TARGET" "$HERE/k6/spike.js"
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 99 ] || { echo "k6 failed (rc=$rc)" >&2; exit "$rc"; }
    echo "load results: $LOAD_JSON"
    ;;
  locust)
    locust -f "$HERE/locust/locustfile.py" --headless --host "$TARGET" \
      --csv "$OUT/${LABEL}_load" --only-summary
    echo "load results: $OUT/${LABEL}_load_stats.csv"
    ;;
  *)
    echo "unknown tool: $TOOL (use k6 or locust)" >&2
    exit 2
    ;;
esac

echo "replica timeline: $REPLICAS_CSV"
