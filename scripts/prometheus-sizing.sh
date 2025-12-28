#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-9090}"

cleanup() {
  if [[ -n "${PF_PID:-}" ]]; then
    kill "$PF_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

kubectl port-forward deploy/prometheus "${PORT}:9090" >/dev/null 2>&1 &
PF_PID=$!

sleep 1

query() {
  local expr="$1"
  curl -s "http://localhost:${PORT}/api/v1/query" --data-urlencode "query=${expr}" |
    python3 - <<'PY'
import json,sys
try:
    data=json.load(sys.stdin)
    result=data["data"]["result"]
    if not result:
        print("0")
    else:
        print(result[0]["value"][1])
except Exception:
    print("0")
PY
}

SERIES=$(query "prometheus_tsdb_head_series")
CHUNKS=$(query "prometheus_tsdb_head_chunks")
RATE=$(query "rate(prometheus_tsdb_head_samples_appended_total[5m])")

POD=$(kubectl get pod -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
DISK=$(kubectl exec "$POD" -- sh -c 'du -sh /prometheus 2>/dev/null | cut -f1')

cat <<OUT
Prometheus sizing snapshot
- head series: ${SERIES}
- head chunks: ${CHUNKS}
- sample append rate (per sec): ${RATE}
- disk used in /prometheus: ${DISK}

Rule of thumb: measure 24h disk growth and multiply by retention window.
OUT
