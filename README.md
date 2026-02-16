# iYup

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.29-blue)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-supported-blue)
![Prometheus](https://img.shields.io/badge/Prometheus-2.54-orange)
![Grafana](https://img.shields.io/badge/Grafana-latest-informational)
![Go](https://img.shields.io/badge/Go-1.23-00ADD8)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)

Lightweight, self-hosted uptime and latency monitoring. Deploy with Docker Compose or on Kubernetes and monitor your endpoints with Prometheus metrics, Grafana dashboards, and a JSON API — no managed services required.

## What You Get

- **Real-time status** — Know instantly if your services are up or down via `/status`
- **Latency percentiles** — p50, p95, p99 response times per target
- **Availability tracking** — Lifetime and windowed (5m, 1h, 24h, 7d) availability percentages
- **Prometheus-native** — All metrics in standard Prometheus format, ready for your existing stack
- **Grafana dashboards** — Pre-configured panels for uptime, latency, and alerting
- **Alerting** — Alertmanager integration for email/webhook/Slack notifications
- **REST API** — JSON endpoints for integrating with dashboards, status pages, or CI/CD
- **Retry with backoff** — Transient failures don't immediately trigger alerts

## Architecture

```
Targets (your services)
    | ping
ping-agent (Go) --> /metrics --> Prometheus --> Grafana
    | reads                           |
api-gateway (FastAPI) <-- JSON API   Alertmanager --> notifications
```

| Component | Purpose |
|-----------|---------|
| **ping-agent** | Concurrent HTTP pinger with retry logic (Go) |
| **api-gateway** | REST API aggregating metrics into JSON (Python/FastAPI) |
| **Prometheus** | Time-series metrics storage and alerting rules |
| **Grafana** | Dashboard visualization |
| **Alertmanager** | Alert routing to email, Slack, webhooks |

## Quick Start

### Option 1: Docker Compose (recommended for trying it out)

```bash
# Monitor your own endpoints
echo 'PING_TARGET_URLS=https://your-api.com,https://your-app.com' > .env

# Start everything
docker compose up -d

# Check status
curl http://localhost:8080/status
```

That's it. Services are available at:
- **API** — http://localhost:8080
- **Grafana** — http://localhost:3000 (admin/admin)
- **Prometheus** — http://localhost:9090

### Option 2: Kubernetes with Helm

```bash
# Start cluster
minikube start

# Build and deploy
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
helm install iyup ./charts/iyup

# Access the API
kubectl port-forward svc/iyup-api-gateway 8080:80
curl http://localhost:8080/status
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /status` | Real-time up/down status, latency, and availability per target |
| `GET /targets` | List all monitored URLs |
| `GET /targets/{url}` | Detailed metrics for a single target (latency percentiles, success/failure counts) |
| `GET /uptime-summary` | Lifetime availability across all targets |
| `GET /uptime-summary-windowed?window=1h` | Windowed availability (requires Prometheus) |
| `GET /healthz` | Health check |
| `GET /metrics` | Prometheus metrics export |

### Example: `/status` response

```json
{
  "status": "operational",
  "targets": [
    {
      "url": "https://google.com",
      "up": true,
      "latency_ms": 45.2,
      "availability": 99.98,
      "total_checks": 2847,
      "latency_percentiles_ms": {
        "p50": 42.1,
        "p95": 89.3,
        "p99": 152.7
      }
    }
  ]
}
```

## Configuration

### Targets

**Docker Compose** — set in `.env`:
```bash
PING_TARGET_URLS=https://your-api.com,https://your-app.com
```

**Kubernetes** — set in `charts/iyup/values.yaml`:
```yaml
pingTargets:
  - https://your-api.com
  - https://your-app.com
```

### All Options

| Variable | Default | Description |
|----------|---------|-------------|
| `PING_TARGET_URLS` | `google.com,github.com` | Comma-separated target URLs |
| `PING_INTERVAL_SECONDS` | `30` | Seconds between ping cycles |
| `PING_CONCURRENCY` | `5` | Parallel ping workers |
| `PING_RETRY_COUNT` | `2` | Retries before marking a target down |
| `PING_HTTP_METHOD` | `GET` | HTTP method (GET/HEAD) |
| `PING_RANGE_REQUEST` | `true` | Use Range header to minimize bandwidth |
| `PROMETHEUS_URL` | auto-configured | Prometheus base URL (enables windowed queries) |
| `PROMETHEUS_QUERY_CACHE_SECONDS` | `15` | Cache TTL for Prometheus queries |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `GRAFANA_PASSWORD` | `admin` | Grafana admin password (Docker Compose only) |
| `PROMETHEUS_RETENTION` | `14d` | Prometheus data retention period |

## Documentation

- **[Quickstart Guide](docs/QUICKSTART.md)** — Get running in 5 minutes
- **[Deployment Guide](docs/DEPLOYMENT.md)** — Helm charts and configuration
- **[Architecture](docs/ARCHITECTURE.md)** — System design and data flows
- **[API Reference](docs/API.md)** — Full endpoint documentation
- **[Grafana Setup](docs/GRAFANA.md)** — Dashboard configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** — Common issues and solutions
- **[Reliability & Testing](docs/RELIABILITY.md)** — Testing infrastructure
- **[Data Validation](docs/DATA_VALIDATION.md)** — Prometheus data quality checks
- **[Command Reference](docs/REFERENCE.md)** — Commands and cheat sheets

## Project Structure

```
iYup/
├── services/
│   ├── ping-agent/       # Go HTTP pinger with Prometheus metrics
│   └── api-gateway/      # FastAPI JSON API
├── config/               # Prometheus, Alertmanager, Grafana configs (Docker Compose)
├── charts/iyup/          # Helm chart (Kubernetes deployment)
├── monitoring/           # Grafana dashboards
├── scripts/              # Utility and testing scripts
└── docs/                 # Documentation
```

## License

MIT — use it however you want.
