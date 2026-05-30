#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
HELPER_NAME="iyup-flaky-demo"
restore_stack=0

if docker compose ps --services --status running | grep -q .; then
  restore_stack=1
fi

pass() {
  printf 'PASS %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  exit 1
}

cleanup() {
  docker rm -f "$HELPER_NAME" >/dev/null 2>&1 || true
  docker compose down >/dev/null 2>&1 || true
  unset PING_TARGET_URLS PING_INTERVAL_SECONDS PING_RETRY_COUNT
  if [[ "$restore_stack" -eq 1 ]]; then
    docker compose up -d >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

export PING_TARGET_URLS="http://$HELPER_NAME:8080"
export PING_INTERVAL_SECONDS="5"
export PING_RETRY_COUNT="2"

docker compose up -d --force-recreate ping-agent api-gateway >/dev/null

ping_agent_cid="$(docker compose ps -q ping-agent)"
network_name="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' "$ping_agent_cid")"

docker run -d --rm \
  --name "$HELPER_NAME" \
  --network "$network_name" \
  -v "$ROOT_DIR/scripts/reliability:/opt/reliability:ro" \
  python:3.11-alpine \
  python /opt/reliability/flaky_http_server.py >/dev/null

docker compose restart ping-agent api-gateway >/dev/null

api_ready=0
for _ in {1..30}; do
  if curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz" >/dev/null 2>&1; then
    pass "api health"
    api_ready=1
    break
  fi
  sleep 2
done

[[ "$api_ready" -eq 1 ]] || fail "api health"

status_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/status")"
metrics_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics")"

python3 - "$status_body" "$metrics_body" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
metrics = sys.argv[2]
targets = payload.get("targets", [])
assert targets, "no targets returned"
target = targets[0]
assert target["url"] == "http://iyup-flaky-demo:8080", target
assert target["up"] is True, target
assert target["total_checks"] >= 1, target
assert target["availability"] == 100.0, target
assert "api_gateway_requests_total" in metrics, "missing API metrics"
PY

pass "transient retry stays up after recovery"
pass "verification completed"
