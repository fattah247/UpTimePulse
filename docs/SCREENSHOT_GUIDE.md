# Screenshot Guide

Load the local ports before capturing anything:

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"
```

Then capture the files in `docs/screenshots/`.

| File | Command or URL | What it proves | Capture note |
|---|---|---|---|
| `docs/screenshots/01-repo-overview.png` | `tree -L 2 -I '.git\|__pycache__\|node_modules'` and `sed -n '1,18p' README.md` | The repo layout and top-level docs are understandable at a glance | Keep the README title and key folders visible |
| `docs/screenshots/02-docker-compose-stack.png` | `docker compose ps` | The local monitoring stack is running | Capture all containers and their health state |
| `docs/screenshots/03-api-healthz.png` | `curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"` | The API gateway health endpoint responds | Capture the command and the JSON body |
| `docs/screenshots/04-api-status-response.png` | `curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" \| jq '{status, targets: [.targets[] \| {url, up, latency_ms, availability, total_checks, latency_percentiles_ms}]}'` | The status API returns target state, latency, and availability data | Keep one full target object visible |
| `docs/screenshots/05-prometheus-targets.png` | `http://localhost:${PROMETHEUS_PORT}/targets` | Prometheus is scraping the expected jobs | Keep `api-gateway` and `ping-agent` rows visible |
| `docs/screenshots/06-prometheus-metrics.png` | `http://localhost:${PROMETHEUS_PORT}/graph?g0.expr=ping_up&g0.tab=1` | Prometheus can query the exported metrics | Show the current `ping_up` vector result |
| `docs/screenshots/07-grafana-dashboard.png` | `http://localhost:${GRAFANA_PORT}` | Grafana dashboard support is real | Sign in and open the `iYup Dashboard` before capturing |
| `docs/screenshots/08-alertmanager.png` | `http://localhost:${ALERTMANAGER_PORT}` | Alertmanager is reachable and part of the local stack | Capture the main alerts page or status page |
| `docs/screenshots/09-helm-template.png` | `helm template iyup ./charts/iyup --show-only templates/grafana-deployment.yaml | sed -n '1,30p'` | Helm packaging renders successfully | Capture a safe manifest section and avoid rendering secrets into the screenshot |
| `docs/screenshots/10-local-verification.png` | `./scripts/verify-local.sh` | The local verification flow is repeatable | Capture the full PASS output in one terminal view if possible |
