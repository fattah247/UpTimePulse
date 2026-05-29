# Screenshot Guide

Use these commands and URLs to capture the portfolio screenshots.

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"
```

| File | Command or URL | What it proves | Capture note |
|---|---|---|---|
| `docs/screenshots/01-repo-overview.png` | `tree -L 2 -I '.git\|__pycache__\|node_modules'` and `sed -n '1,18p' README.md` | repo layout and first screen | keep the title and docs list visible |
| `docs/screenshots/02-docker-compose-stack.png` | `docker compose ps` | local stack is up | keep all services visible |
| `docs/screenshots/03-api-healthz.png` | `curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"` | API health endpoint works | capture the JSON body |
| `docs/screenshots/04-api-status-response.png` | `curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" \| jq '{status, targets: [.targets[] \| {url, up, latency_ms, availability, total_checks, latency_percentiles_ms}]}'` | status API returns live monitoring data | keep one full target object visible |
| `docs/screenshots/05-prometheus-targets.png` | `http://localhost:${PROMETHEUS_PORT}/targets` | Prometheus is scraping the jobs | keep `api-gateway` and `ping-agent` visible |
| `docs/screenshots/06-prometheus-metrics.png` | `http://localhost:${PROMETHEUS_PORT}/graph?g0.expr=ping_up&g0.tab=1` | Prometheus query returns real metrics | show the current vector result |
| `docs/screenshots/07-grafana-dashboard.png` | `http://localhost:${GRAFANA_PORT}` | Grafana dashboard is provisioned and readable | open `iYup Dashboard` before capturing |
| `docs/screenshots/08-alertmanager.png` | `http://localhost:${ALERTMANAGER_PORT}` | Alertmanager is reachable | capture the alerts page or status page |
| `docs/screenshots/09-helm-template.png` | `helm template iyup ./charts/iyup --show-only templates/grafana-deployment.yaml \| sed -n '1,30p'` | Helm rendering works | avoid secret output |
| `docs/screenshots/10-local-verification.png` | `./scripts/verify-local.sh` | local verification is repeatable | keep the full PASS list visible |
