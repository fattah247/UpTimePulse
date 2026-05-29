#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"

pass() {
  printf 'PASS %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-30}"
  local delay="${4:-2}"

  for ((i = 0; i < attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      pass "$name"
      return 0
    fi
    sleep "$delay"
  done

  fail "$name"
}

assert_contains() {
  local name="$1"
  local body="$2"
  local needle="$3"

  [[ "$body" == *"$needle"* ]] || fail "$name"
}

has_service() {
  local name="$1"
  printf '%s\n' "$COMPOSE_SERVICES" | grep -qx "$name"
}

require_cmd docker
require_cmd curl

COMPOSE_SERVICES="$(docker compose config --services)"
docker compose config >/dev/null
pass "docker compose config"

docker compose up -d >/dev/null 2>&1
pass "docker compose up"

wait_for_http "api healthz" "http://localhost:${API_GATEWAY_PORT}/healthz"

healthz_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz")"
assert_contains "api healthz body" "$healthz_body" '"status"'
pass "api healthz body"

status_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/status")"
assert_contains "status endpoint" "$status_body" '"targets"'
pass "status endpoint"

targets_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/targets")"
assert_contains "targets endpoint" "$targets_body" '"url"'
pass "targets endpoint"

metrics_body="$(curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics")"
assert_contains "metrics endpoint" "$metrics_body" 'api_gateway_requests_total'
pass "metrics endpoint"

if has_service prometheus; then
  wait_for_http "prometheus ready" "http://localhost:${PROMETHEUS_PORT}/-/ready"
fi

if has_service grafana; then
  wait_for_http "grafana ready" "http://localhost:${GRAFANA_PORT}/login"
fi

if has_service alertmanager; then
  wait_for_http "alertmanager ready" "http://localhost:${ALERTMANAGER_PORT}/-/ready"
fi
