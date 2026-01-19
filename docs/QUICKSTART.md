# Quickstart Guide

Get iYup up and running in minutes.

## Prerequisites

- Docker (Desktop or Engine)
- kubectl
- Helm
- Minikube (for local cluster)
- Go 1.23+ (for ping-agent development)
- Python 3.11+ (for api-gateway development)

## Option 1: Local Docker (Ping Agent Only)

Run ping-agent locally:

```bash
cd services/ping-agent
docker build -t ping-agent:dev .
docker run --rm ping-agent:dev
```

## Option 2: Full Stack in Minikube

### 1. Start Minikube

```bash
minikube start
kubectl config use-context minikube
```

### 2. Build Images

```bash
# Point Docker at Minikube's daemon
eval $(minikube -p minikube docker-env)

# Build images
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
```

### 3. Deploy with Helm

```bash
helm install iyup ./charts/iyup
```

### 4. Access Services

```bash
# Ping Agent metrics
kubectl port-forward svc/iyup-ping-agent 18080:8080

# API Gateway
kubectl port-forward svc/iyup-api-gateway 8080:80

# Prometheus
kubectl port-forward svc/iyup-prometheus 9090:9090

# Grafana
kubectl port-forward svc/iyup-grafana 3000:3000
```

### 5. Test

In another terminal:

```bash
# Check ping-agent metrics
curl http://localhost:18080/metrics

# Check API gateway health
curl http://localhost:8080/healthz

# Get uptime summary
curl http://localhost:8080/uptime-summary
```

## Option 3: Local Development (API Gateway)

Run the FastAPI gateway outside Kubernetes:

```bash
cd services/api-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export PING_AGENT_METRICS_URL="http://localhost:8080/metrics"
export PING_TARGET_URLS="https://google.com,https://github.com"
export PROMETHEUS_URL="http://localhost:9090"
export PROMETHEUS_QUERY_CACHE_SECONDS="15"
export API_GATEWAY_PORT="8081"

# Run
uvicorn main:app --host 0.0.0.0 --port "${API_GATEWAY_PORT}"
```

You can also use `.env` file (see `.env.example`).

## Remove Stack

```bash
helm uninstall iyup
```

## Next Steps

- [Deployment Guide](DEPLOYMENT.md) - Configure and customize your deployment
- [API Reference](API.md) - Learn about available endpoints
- [Grafana Setup](GRAFANA.md) - Set up dashboards and visualization
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Architecture](ARCHITECTURE.md) - Understand the system design
