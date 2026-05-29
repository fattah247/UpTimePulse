# API

Load local ports first:

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
```

Base URL:

```text
http://localhost:${API_GATEWAY_PORT}
```

## Endpoints

| Method | Path | What it returns |
|---|---|---|
| `GET` | `/healthz` | simple API health check |
| `GET` | `/targets` | configured target list |
| `GET` | `/status` | target state, latency, percentiles, and availability |
| `GET` | `/targets/{target_url}` | per-target detail for one URL |
| `GET` | `/uptime-summary` | lifetime success, failure, and availability |
| `GET` | `/uptime-summary-windowed?window=5m` | Prometheus-backed uptime window |
| `GET` | `/metrics` | Prometheus metrics for the API gateway |

## Commands

Health:

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"
```

Targets:

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/targets" | python3 -m json.tool
```

Status:

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" | python3 -m json.tool
```

Windowed uptime:

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/uptime-summary-windowed?window=5m" | python3 -m json.tool
```

Metrics:

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics"
```
