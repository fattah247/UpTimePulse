# Phase 0 Verification

Checked on `2026-05-29`.

This pass verified that the local stack starts and that the documented monitoring surfaces are real.

The machine used for this pass had `API_GATEWAY_PORT=8081` in `.env`, so the API commands below use `localhost:8081`. The documented default is still `8080`.

| Claim | Status | Evidence command | Result | Follow-up |
|---|---|---|---|---|
| Docker Compose starts the stack | Verified | `docker compose config`<br>`docker compose up -d --remove-orphans`<br>`docker compose ps` | Compose resolved cleanly and started `ping-agent`, `api-gateway`, `prometheus`, `grafana`, and `alertmanager`. | Removed an undocumented `loki` service and made host ports configurable through `.env`. |
| API gateway starts | Verified | `docker compose ps` | `uptimepulse-api-gateway-1` reached healthy state. | None. |
| ping-agent starts | Verified | `docker compose ps` | `uptimepulse-ping-agent-1` reached healthy state. | None. |
| Prometheus starts | Verified | `docker compose ps`<br>`curl -fsS http://localhost:9090/-/ready` | Prometheus started and returned `Prometheus Server is Ready.` | None. |
| Grafana starts | Verified | `docker compose ps`<br>`curl -fsS http://localhost:3000/login` | Grafana became reachable on port `3000`. | None. |
| Alertmanager starts if included | Verified | `docker compose ps`<br>`curl -fsS http://localhost:9093/-/ready` | Alertmanager started and returned `OK`. | None. |
| `/healthz` works | Verified | `curl -fsS http://localhost:8081/healthz` | Returned `{"status":"ok"}`. | None. |
| `/status` works | Verified | `curl -fsS http://localhost:8081/status` | Returned `status="operational"` with target status, latency, percentiles, and availability data. | None. |
| `/targets` works | Verified | `curl -fsS http://localhost:8081/targets` | Returned the configured targets list. | None. |
| `/metrics` works | Verified | `curl -fsS http://localhost:8081/metrics` | Returned Prometheus-formatted API gateway metrics, including `api_gateway_requests_total`. | None. |
| Prometheus can scrape metrics | Verified | `curl -fsS http://localhost:9090/api/v1/targets`<br>`curl -fsS 'http://localhost:9090/api/v1/query?query=ping_up'` | Both `api-gateway` and `ping-agent` targets were `health="up"`. Prometheus query returned `ping_up=1` for both default targets. | None. |
| Grafana dashboard files exist and are provisioned if documented | Partially verified | `curl -fsS -u admin:admin http://localhost:3000/api/search` | Docker Compose now auto-provisions the included `iYup Dashboard`. | Helm chart rendering is verified separately, but Helm dashboard provisioning is still manual/partial. |
| Alertmanager config exists and is wired if documented | Verified | `curl -fsS http://localhost:9090/api/v1/rules`<br>`curl -fsS http://localhost:9093/api/v2/status` | Prometheus loaded `TargetDown` from `/etc/prometheus/rules/alert.rules.yml`, and Alertmanager reported a ready cluster with the loaded route config. | Default receiver has no real outbound credentials; webhook/email examples remain placeholders only. |
| Kubernetes/Helm chart renders if documented | Verified | `helm lint ./charts/iyup`<br>`helm template iyup ./charts/iyup` | Helm lint passed and the chart rendered successfully. | Phase 0 validates rendering only; no live cluster behavior is claimed here. |
| Default target configuration works | Verified | `curl -fsS http://localhost:8081/targets` | Returned the default target set: `https://google.com` and `https://github.com`. | None. |
| Custom target configuration works through environment variables | Verified | `env PING_TARGET_URLS='https://example.com,https://example.org' docker compose up -d --no-build ping-agent api-gateway`<br>`curl -fsS http://localhost:8081/targets` | Returned the overridden targets `https://example.com` and `https://example.org`. | Target changes require container recreate; there is no live reload path. |
| Retry/backoff behavior exists if claimed | Verified | `rg -n 'PING_RETRY_COUNT|backoff :=|Retry\\(|backoff_factor' services/ping-agent/main.go services/api-gateway/main.py` | `ping-agent` uses exponential backoff between retry attempts, and `api-gateway` uses `urllib3 Retry` with `total=3` and `backoff_factor=0.3` for upstream requests. | Verified by source inspection, not by a fault-injection runtime test. |
| Latency percentiles exist if claimed | Verified | `curl -fsS http://localhost:8081/status`<br>`curl -fsS 'http://localhost:8081/targets/https%3A%2F%2Fgoogle.com'` | Both endpoints returned `latency_percentiles_ms` with `p50`, `p95`, and `p99`. | None. |
| Availability windows exist if claimed | Verified | `curl -fsS 'http://localhost:8081/uptime-summary-windowed?window=5m'` | Returned windowed success, failure, and availability data for the current targets. | Short-window counts can be fractional because Prometheus `increase()` extrapolates counter deltas. |
| Tests exist and pass, or document what is missing | Verified | `go test ./...`<br>`python -m unittest discover -s services/api-gateway -p 'test*.py'` | Go tests passed (`3` tests). Python tests passed (`21` tests). | Minimal Go coverage was added for target parsing and default target behavior. |
