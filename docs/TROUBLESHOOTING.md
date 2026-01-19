# Troubleshooting Guide

Common issues and their solutions when working with iYup.

## Goal

Run the ping-agent in Docker and in Minikube, expose Prometheus metrics on `:8080/metrics`, and verify it with `curl`.

## Common Problems

### Docker Issues

**Problem:** Docker couldn't connect to the daemon

**Solutions:**
- Start Docker Desktop
- Reset Docker env: `eval $(minikube docker-env -u)` when switching between local and Minikube
- Check Docker is running: `docker ps`

---

### Kubernetes Image Issues

**Problem:** `ErrImageNeverPull` in Kubernetes (image not available inside Minikube)

**Solution:**
Build the image inside Minikube:
```bash
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
```

---

### Helm Issues

**Problem:** Helm install failed from wrong working directory

**Solution:**
Always run from repo root:
```bash
cd /path/to/iYup
helm install iyup ./charts/iyup
```

**Problem:** Helm template parse errors (escaped quotes)

**Solution:**
Use single-quoted strings in Helm templates (avoid `\"`).

---

### Port-Forward Issues

**Problem:** Port-forward to `:8080` returned `connection refused`

**Solution:**
- Check pod is running: `kubectl get pods`
- Verify pod has the latest image (restart if needed)
- Check pod logs: `kubectl logs <pod-name>`

**Problem:** Port-forward to API gateway failed (Service exposed port 80, not 8080)

**Solution:**
Use correct port mapping:
```bash
kubectl port-forward svc/iyup-api-gateway 8080:80
```

Or set `service.apiGatewayPort: 8080` in values.yaml.

---

### Metrics Issues

**Problem:** `/uptime-summary` returned `0%` availability even though `/metrics` showed success counts

**Solution:**
The metrics parser was too strict. Fixed by reading label values like `target="..."` and summing `ping_success_total{target="..."}` and `ping_failure_total{target="..."}` per target.

**Problem:** `/uptime-summary` inflated availability when Prometheus `_created` samples were parsed as real counters

**Solution:**
Tighten Prometheus parsing to match exact metric names and skip `_created` samples.

---

### Build Issues

**Problem:** Go build errors (missing `go.sum`, Go version mismatch, syntax errors)

**Solutions:**
- Ensure `go.sum` is present (required for Docker builds)
- Use correct Go version (1.23+)
- Check syntax: `go vet ./...`
- Run tests: `go test ./...`

**Problem:** Python tests reported "NO TESTS RAN" because test file was missing

**Solution:**
Ensure `test_main.py` exists in `services/api-gateway/`.

---

### Prometheus/Grafana Issues

**Problem:** Prometheus/Grafana rollouts stuck due to PVC lock during rolling updates

**Solution:**
Use `strategy: Recreate` for Prometheus/Grafana when using PVCs, then delete old pods so only one holds the lock.

**Problem:** Grafana panels go blank briefly during Prometheus rollouts

**Solution:**
This is normal. Give it ~30 seconds for Prometheus to stabilize.

**Problem:** Grafana rollouts keep hanging

**Solution:**
Set `strategy: Recreate` in `charts/iyup/templates/grafana-deployment.yaml`.

---

### Alerting Issues

**Problem:** Alerts not visible

**Solution:**
Check alert-logger pod logs:
```bash
kubectl logs deploy/iyup-alert-logger --tail=50
```

Verify alert rules exist:
```bash
# Check Prometheus alerts
curl http://localhost:9090/api/v1/alerts

# Check Alertmanager
open http://localhost:9093/#/alerts
```

---

### Performance Issues

**Problem:** ping-agent kept sockets open after requests, causing poor connection reuse

**Solution:**
Drain response bodies and close them to keep HTTP connections reusable.

**Problem:** Sequential pinging can stretch the 30s interval if any target is slow or hangs

**Solution:**
Use a bounded worker pool or concurrent checks to keep the polling interval predictable.

**Problem:** Draining full response bodies can delay the loop when targets return large payloads

**Solution:**
Switch to `HEAD` or cap body reads to avoid large payload delays (use `PING_BODY_MAX_BYTES`).

---

### Configuration Issues

**Problem:** Target list is loaded only at startup, so ConfigMap/env changes require a restart

**Solution:**
Add periodic reload or SIGHUP handler to refresh target lists without a restart. (Currently requires restart.)

**Problem:** `/uptime-summary` uses lifetime counters, which can mask recent outages

**Solution:**
Use `/uptime-summary-windowed?window=5m` for current uptime over a time window.

---

## Verification Steps

### Check Services Are Running

```bash
# Check pods
kubectl get pods

# Check services
kubectl get svc

# Check logs
kubectl logs -l app.kubernetes.io/component=ping-agent --tail=20
kubectl logs -l app.kubernetes.io/component=api-gateway --tail=20
```

### Verify Metrics

```bash
# Ping agent metrics
kubectl port-forward svc/iyup-ping-agent 18080:8080
curl -v http://localhost:18080/metrics

# API gateway metrics
kubectl port-forward svc/iyup-api-gateway 8080:80
curl -v http://localhost:8080/metrics
```

### Verify API Endpoints

```bash
# Health check
curl http://localhost:8080/healthz

# Uptime summary
curl http://localhost:8080/uptime-summary | jq

# Targets
curl http://localhost:8080/targets | jq
```

### Verify Prometheus

```bash
# Check targets
open http://localhost:9090/targets

# Check alerts
open http://localhost:9090/alerts

# Check rules
open http://localhost:9090/rules
```

### Verify PVCs

```bash
# Check PVC status
kubectl get pvc

# Should show Bound status for prometheus-pvc and grafana-pvc
```

## Getting Help

1. Check pod logs: `kubectl logs <pod-name>`
2. Check service status: `kubectl describe svc <service-name>`
3. Check deployment: `kubectl describe deployment <deployment-name>`
4. Check events: `kubectl get events --sort-by='.lastTimestamp'`

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started
- [Deployment Guide](DEPLOYMENT.md) - Configuration options
- [Architecture](ARCHITECTURE.md) - Understanding the system
- [API Reference](API.md) - API endpoints
