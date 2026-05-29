# iYup

![Docker Compose](https://img.shields.io/badge/Docker_Compose-supported-blue)
![Prometheus](https://img.shields.io/badge/Prometheus-2.54-orange)
![Grafana](https://img.shields.io/badge/Grafana-supported-F46800)
![Helm](https://img.shields.io/badge/Helm-rendered-0F1689)
![Go](https://img.shields.io/badge/Go-1.23-00ADD8)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)

`iYup` is a small uptime monitoring stack built around active HTTP checks, a JSON status API, and Prometheus-compatible metrics. It is intended as a practical SRE/platform portfolio project, not a full observability platform.

## What It Does

- Runs active HTTP checks from `ping-agent`
- Exposes operational status through `api-gateway`
- Publishes Prometheus metrics from both services
- Starts a local monitoring stack with Docker Compose
- Provisions a Grafana datasource and dashboard in Docker Compose
- Wires Prometheus alert rules to Alertmanager
- Packages the stack as a Helm chart that renders cleanly

## Quick Start

```bash
cp .env.example .env
```

Set `PING_TARGET_URLS` in `.env` to the endpoints you want to monitor. If a default host port is already in use, change the matching `*_PORT` value in `.env`.

```bash
docker compose up -d
./scripts/verify-local.sh
```

Default local endpoints:

- API: `http://localhost:8080`
- Ping metrics: `http://localhost:18080/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Alertmanager: `http://localhost:9093`

If you override ports in `.env`, use those values instead. The verification script reads `.env` before it checks the stack.

## Verification

```bash
./scripts/verify-local.sh
```

The script:

- validates `docker compose config`
- starts the local stack
- waits for API readiness
- checks `/healthz`, `/status`, `/targets`, and `/metrics`
- checks Prometheus readiness
- checks Grafana and Alertmanager availability when those services are in Compose

Detailed phase-0 results are tracked in [docs/PHASE_0_VERIFICATION.md](docs/PHASE_0_VERIFICATION.md).

## API Surface

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | API health check |
| `GET /status` | Current target status, last latency, percentiles, and availability |
| `GET /targets` | Target list derived from `PING_TARGET_URLS` |
| `GET /targets/{url}` | Per-target details, including latency percentiles |
| `GET /uptime-summary` | Lifetime success, failure, and availability from ping-agent counters |
| `GET /uptime-summary-windowed?window=5m` | Windowed availability from Prometheus queries |
| `GET /metrics` | Prometheus metrics for the API gateway |

`/uptime-summary-windowed` uses Prometheus `increase()`, so short windows can return fractional success and failure values.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PING_TARGET_URLS` | `https://google.com,https://github.com` | Comma-separated target URLs |
| `PING_INTERVAL_SECONDS` | `30` | Ping cadence |
| `PING_CONCURRENCY` | `5` | Parallel ping workers |
| `PING_RETRY_COUNT` | `2` | Additional ping retries before marking a target down |
| `PING_HTTP_METHOD` | `GET` | Request method |
| `PING_RANGE_REQUEST` | `true` | Sends `Range: bytes=0-0` on `GET` requests |
| `PROMETHEUS_QUERY_CACHE_SECONDS` | `15` | API cache TTL for Prometheus-backed window queries |
| `PING_AGENT_PORT` | `18080` | Host port for ping-agent metrics |
| `API_GATEWAY_PORT` | `8080` | Host port for the API gateway |
| `PROMETHEUS_PORT` | `9090` | Host port for Prometheus |
| `GRAFANA_PORT` | `3000` | Host port for Grafana |
| `ALERTMANAGER_PORT` | `9093` | Host port for Alertmanager |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password for Docker Compose |
| `PROMETHEUS_RETENTION` | `14d` | Prometheus retention period |

## What This Proves for SRE / Platform Roles

- active health checks against configurable HTTP targets
- Prometheus metric exposure from both the checker and the API layer
- availability and latency visibility, including percentile summaries
- Grafana dashboard provisioning in local Docker Compose
- Alertmanager routing path from Prometheus rule evaluation to receiver config
- Docker Compose local operations with health-gated startup
- Kubernetes manifest and Helm render validation
- API surface that can feed status integrations or operational tooling

## Limitations

- does not replace managed observability platforms
- does not provide distributed tracing
- does not provide log aggregation
- does not guarantee production-grade alert tuning
- does not include real notification credentials
- does not implement incident management workflows
- not multi-region
- Helm rendering is validated in Phase 0, but no live Kubernetes cluster verification is claimed here

## Project Layout

```text
iYup/
├── services/
│   ├── ping-agent/
│   └── api-gateway/
├── config/
├── monitoring/
├── charts/iyup/
├── scripts/
└── docs/
```

## Documentation

- [docs/PHASE_0_VERIFICATION.md](docs/PHASE_0_VERIFICATION.md)
- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/API.md](docs/API.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/GRAFANA.md](docs/GRAFANA.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
