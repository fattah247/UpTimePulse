# Screenshot Guide

Use this guide to capture a consistent Phase 1 proof set. If your `.env` overrides host ports, substitute those values in the URLs below.

| File | Command or URL | What it proves | Capture note |
|---|---|---|---|
| `docs/screenshots/01-repo-overview.png` | Open the repository root in GitHub or your editor | The repo layout and top-level docs are understandable at a glance | Keep the README title and key folders visible |
| `docs/screenshots/02-docker-compose-stack.png` | `docker compose ps` | The local monitoring stack is running | Capture all containers and their health state |
| `docs/screenshots/03-api-healthz.png` | `curl -fsS http://localhost:8080/healthz` | The API gateway health endpoint responds | Use the port from `.env` if overridden |
| `docs/screenshots/04-api-status-response.png` | `curl -fsS http://localhost:8080/status | jq .` | The status API returns target state, latency, and availability data | Use `jq` if available for readability |
| `docs/screenshots/05-prometheus-targets.png` | `http://localhost:9090/targets` | Prometheus is scraping the expected jobs | Keep `api-gateway` and `ping-agent` rows visible |
| `docs/screenshots/06-prometheus-metrics.png` | `http://localhost:9090/graph?g0.expr=ping_up&g0.tab=1` | Prometheus can query the exported metrics | Show the current `ping_up` vector result |
| `docs/screenshots/07-grafana-dashboard.png` | `http://localhost:3000` | Grafana dashboard support is real | Sign in and open the `iYup Dashboard` before capturing |
| `docs/screenshots/08-alertmanager.png` | `http://localhost:9093` | Alertmanager is reachable and part of the local stack | Capture the main alerts page or status page |
| `docs/screenshots/09-helm-template.png` | `helm template iyup ./charts/iyup` | Helm packaging renders successfully | Capture the first visible manifests and the command line |
| `docs/screenshots/10-local-verification.png` | `./scripts/verify-local.sh` | The local verification flow is repeatable | Capture the full PASS output in one terminal view if possible |
