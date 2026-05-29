# Portfolio Proof Checklist

This file tracks the proof assets for iYup. A row is marked verified only when there is a command result, screenshot, or verification note that backs it up.

| Proof area | Status | Evidence | Notes |
|---|---|---|---|
| Docker Compose stack | Verified | `./scripts/verify-local.sh`, `docker compose ps`, `docs/screenshots/02-docker-compose-stack.png` | Local stack starts through Docker Compose |
| API health endpoint | Verified | `curl /healthz`, `docs/screenshots/03-api-healthz.png` | API host port follows `.env` when overridden |
| Status API | Verified | `curl /status`, `docs/screenshots/04-api-status-response.png` | Shows target state, latency, and availability |
| Prometheus scrape targets | Verified | Prometheus targets page, `docs/screenshots/05-prometheus-targets.png` | Shows `api-gateway` and `ping-agent` as up |
| Prometheus metrics query | Verified | Prometheus graph query, `docs/screenshots/06-prometheus-metrics.png` | Uses the real `ping_up` metric |
| Grafana dashboard | Verified | `docs/screenshots/07-grafana-dashboard.png` | Dashboard is provisioned in Docker Compose and captured from the running stack |
| Alertmanager path | Verified | `docs/screenshots/08-alertmanager.png`, `docs/PHASE_0_VERIFICATION.md` | No real outbound credentials are configured |
| Helm rendering | Verified | `helm lint ./charts/iyup`, `helm template iyup ./charts/iyup`, `docs/screenshots/09-helm-template.png` | Rendering only, no live cluster claim |
| Local verification script | Verified | `./scripts/verify-local.sh`, `docs/screenshots/10-local-verification.png` | Repeatable local verification path |
