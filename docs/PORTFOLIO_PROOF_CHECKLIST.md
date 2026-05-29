# Portfolio Proof Checklist

Use this table to see which repo claims have command output, screenshots, or both.

| Proof area | Status | Evidence | Notes |
|---|---|---|---|
| Docker Compose stack | Verified | `./scripts/verify-local.sh`, `docker compose ps`, `docs/screenshots/02-docker-compose-stack.png` | Local stack starts through Docker Compose |
| API health endpoint | Verified | `curl /healthz`, `docs/screenshots/03-api-healthz.png` | API host port follows `.env` when overridden |
| Status API | Verified | `curl /status`, `docs/screenshots/04-api-status-response.png` | Shows target state, latency, and availability |
| Prometheus scrape targets | Verified | Prometheus targets page, `docs/screenshots/05-prometheus-targets.png` | `api-gateway` and `ping-agent` are up |
| Prometheus metrics query | Verified | Prometheus graph query, `docs/screenshots/06-prometheus-metrics.png` | Uses the real `ping_up` metric |
| Grafana dashboard | Verified | `docs/screenshots/07-grafana-dashboard.png` | Captured from the running Docker Compose stack |
| Alertmanager path | Verified | `docs/screenshots/08-alertmanager.png`, `docs/PHASE_0_VERIFICATION.md` | No real outbound credentials are configured |
| Helm rendering | Verified | `helm lint ./charts/iyup`, `helm template iyup ./charts/iyup`, `docs/screenshots/09-helm-template.png` | Render check only |
| Local verification script | Verified | `./scripts/verify-local.sh`, `docs/screenshots/10-local-verification.png` | Repeatable local verification path |
