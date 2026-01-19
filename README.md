# iYup

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.29-blue)
![Prometheus](https://img.shields.io/badge/Prometheus-2.48-orange)
![Grafana](https://img.shields.io/badge/Grafana-10.3-informational)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)

Uptime + latency monitoring stack built to learn Kubernetes, Prometheus, and Grafana by wiring a real system end to end. No managed services required.

## Quick Overview

**What it does:** Monitors website uptime and latency by pinging targets (like google.com, github.com) and exposing metrics via Prometheus, visualized in Grafana.

**Data flow:** `ping-agent` → `Prometheus` → `Grafana`  
**API flow:** `client` → `api-gateway` → `ping-agent` metrics

```mermaid
flowchart LR
  helm[Helm chart] --> k8s[Kubernetes resources]
  targets[PING_TARGET_URLS] --> ping
  client[Client] --> api[api-gateway]
  api -->|reads metrics| metrics[ping-agent /metrics]
  ping[ping-agent] --> metrics
  prom[Prometheus] --> grafana[Grafana]
  prom -->|scrape| metrics
  prom -->|scrape| api
  alert[Alertmanager] --> logger[alert-logger]
  prom -->|alerts| alert
```

## Documentation

- **[Quickstart Guide](docs/QUICKSTART.md)** - Get started in 5 minutes
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Helm charts, configuration, and deployment
- **[Architecture](docs/ARCHITECTURE.md)** - System design, components, and data flows
- **[API Reference](docs/API.md)** - API endpoints and usage
- **[Grafana Setup](docs/GRAFANA.md)** - Dashboard configuration and visualization
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Reliability & Testing](docs/RELIABILITY.md)** - Reliability improvements and testing
- **[Command Reference](docs/REFERENCE.md)** - Commands, flags, and cheat sheets

## Project Structure

```
iYup/
├── services/          # Application services (ping-agent, api-gateway, dashboard-ui)
├── charts/iyup/      # Helm chart templates and values
├── monitoring/       # Grafana dashboards and Alloy configs
├── scripts/          # Utility scripts (testing, sizing)
├── terraform/        # Infrastructure as code
└── docs/            # Documentation
```

## Prerequisites

- Docker (Desktop or Engine)
- kubectl
- Helm
- Minikube (for local cluster)
- Go 1.23+ (for ping-agent)
- Python 3.11+ (for api-gateway)

## Quick Start

```bash
# Start Minikube
minikube start
kubectl config use-context minikube

# Build images
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway

# Deploy
helm install iyup ./charts/iyup

# Access services
kubectl port-forward svc/iyup-ping-agent 18080:8080
kubectl port-forward svc/iyup-api-gateway 8080:80
```

See [Quickstart Guide](docs/QUICKSTART.md) for detailed instructions.

## Features

- ✅ **Uptime Monitoring** - Track availability of multiple targets
- ✅ **Latency Metrics** - Histogram-based latency tracking
- ✅ **Prometheus Integration** - Full Prometheus metrics export
- ✅ **Grafana Dashboards** - Pre-configured visualization
- ✅ **Alerting** - Alertmanager integration with SMTP/Slack
- ✅ **REST API** - JSON API for uptime summaries
- ✅ **Production Ready** - Retry logic, graceful shutdown, health checks
- ✅ **Comprehensive Testing** - Unit tests + long-running reliability tests

## Reliability & Production Readiness

The system includes comprehensive reliability improvements:

- ✅ **Retry Logic** - Exponential backoff for HTTP requests
- ✅ **Connection Pooling** - Optimized HTTP session management
- ✅ **Error Handling** - Detailed error messages with context
- ✅ **Health Checks** - Kubernetes-ready health endpoints
- ✅ **Graceful Shutdown** - Clean pod termination
- ✅ **Comprehensive Testing** - 11 unit tests + integration tests + reliability tests

See [Reliability & Testing](docs/RELIABILITY.md) for details.

## What I Learned

I built this as a crash course in the stuff that only sticks once it breaks: container builds inside Minikube, Prometheus scraping, Grafana dashboards, and *why rollouts + PVCs can be a pain*. It's a learning stack, not a product, and I'm keeping it around because the failure modes are visible and repeatable.

The system has evolved to include production-ready reliability features, comprehensive testing, and long-term validation capabilities.

## License

This is a learning project. Use it as you wish.
