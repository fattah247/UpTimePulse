# Deployment Guide

Complete guide to deploying and configuring iYup.

## Helm Values Reference

### Common Configuration

These are the values you are most likely to tweak:

- `pingTargets` (list of URLs) - Sets `PING_TARGET_URLS` for both ping-agent and api-gateway
- `service.apiGatewayPort` (default `80`) - Service port for API gateway
- `ingress.enabled`, `ingress.host` - Expose API gateway via Ingress
- `hpa.enabled`, `hpa.minReplicas`, `hpa.maxReplicas` - Auto-scaling configuration

### Ping Agent Runtime Environment

- `PING_INTERVAL_SECONDS` (default `30`) - Ping cycle interval
- `PING_CONCURRENCY` (default `5`) - Number of concurrent checks
- `PING_BODY_MAX_BYTES` (default `65536`) - Max bytes read from response body
- `PING_HTTP_METHOD` (default `GET`) - HTTP method (use `HEAD` for headers-only)
- `PING_RANGE_REQUEST` (default `true`) - Add `Range: bytes=0-0` for GET to minimize body

### API Gateway Runtime Environment

- `PROMETHEUS_URL` - Required for `/uptime-summary-windowed` endpoint
- `PROMETHEUS_QUERY_CACHE_SECONDS` (default `15`) - Cache TTL for Prometheus query results

See `charts/iyup/values.yaml` for the full list.

## Secrets and SMTP (Alertmanager)

SMTP credentials are provided via Helm values (preferred) or a local values file.

### Using Values File

Create `charts/iyup/values.local.yaml` (do not commit):

```yaml
alert:
  smtp:
    user: "you@gmail.com"
    password: "APP_PASSWORD"
    from: "you@gmail.com"
    to: "alerts@example.com"
```

Apply with:

```bash
helm upgrade --install iyup ./charts/iyup -f charts/iyup/values.local.yaml
```

### Using Command Line

```bash
helm upgrade --install iyup ./charts/iyup \
  --set alert.smtp.user="you@gmail.com" \
  --set alert.smtp.password="APP_PASSWORD" \
  --set alert.smtp.from="you@gmail.com" \
  --set alert.smtp.to="alerts@example.com"
```

## Feature Toggles

### Enable Ingress

```yaml
ingress:
  enabled: true
  host: iyup.local
```

### Enable HPA (Horizontal Pod Autoscaler)

```yaml
hpa:
  enabled: true
  minReplicas: 1
  maxReplicas: 3
```

## Full Rebuild Path

### 1. Build Images Inside Minikube

```bash
cd /path/to/iYup
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
```

### 2. Install or Upgrade Helm Chart

```bash
helm upgrade --install iyup ./charts/iyup
```

### 3. Restart Deployments

```bash
kubectl rollout restart deployment iyup-ping-agent
kubectl rollout restart deployment iyup-api-gateway
kubectl rollout restart deployment iyup-prometheus
kubectl rollout restart deployment iyup-grafana

# Wait for readiness
kubectl rollout status deployment iyup-ping-agent
kubectl rollout status deployment iyup-api-gateway
kubectl rollout status deployment iyup-prometheus
kubectl rollout status deployment iyup-grafana
```

### 4. Port-Forward and Test

```bash
kubectl port-forward svc/iyup-ping-agent 18080:8080
kubectl port-forward svc/iyup-api-gateway 8080:80
kubectl port-forward svc/iyup-prometheus 9090:9090
kubectl port-forward svc/iyup-grafana 3000:3000
```

### 5. Verify

```bash
# Health checks
curl http://localhost:8080/healthz
curl http://localhost:18080/healthz

# Metrics
curl http://localhost:18080/metrics
curl http://localhost:8080/uptime-summary

# Prometheus targets
open http://localhost:9090/targets
```

## Helm Sanity Checks

```bash
# Lint the chart
helm lint charts/iyup

# Dry-run template rendering
helm template iyup ./charts/iyup | kubectl apply --dry-run=client -f -
```

## Persistence

Prometheus and Grafana are configured with PVCs so data and dashboards survive restarts. If you redeploy the Pods, your metrics history and Grafana settings should remain.

- Prometheus PVC: `5Gi` (configurable in `values.yaml`)
- Grafana PVC: `5Gi` (configurable in `values.yaml`)
- Retention: `14d` for Prometheus

## Quick Sanity Checks

- Prometheus targets are UP: `http://localhost:9090/targets`
- Alert rule exists: `http://localhost:9090/rules` (look for `TargetDown`)
- Alertmanager is reachable: `http://localhost:9093/#/alerts`
- Alert output shows in logger: `kubectl logs deploy/iyup-alert-logger --tail=50`
- API works: `curl http://localhost:8080/healthz`
- Ping metrics are exposed: `curl http://localhost:18080/metrics`
- PVCs are bound: `kubectl get pvc`

## Trigger an Alert (Quick Test)

1. Set a bad target in `charts/iyup/values.yaml` (e.g., `https://example.invalid`)
2. Apply and wait:
   ```bash
   helm upgrade --install iyup ./charts/iyup
   ```
3. Wait 1–2 minutes, then check:
   - `http://localhost:9090/alerts`
   - `kubectl logs deploy/iyup-alert-logger --tail=50`

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started
- [Architecture](ARCHITECTURE.md) - Understanding the system components
- [Troubleshooting](TROUBLESHOOTING.md) - Common deployment issues
- [API Reference](API.md) - API endpoints
