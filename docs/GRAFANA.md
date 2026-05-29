# Grafana Dashboard Setup

Complete guide to setting up and using Grafana dashboards with iYup.

## Getting Latest Data from Updated Codebase

When you've updated the codebase and want Grafana to show the latest metrics:

### Quick Update Process

```bash
# 1. Rebuild images with latest code
eval $(minikube -p minikube docker-env)  # If using Minikube
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway

# 2. Restart services to use new images
kubectl rollout restart deployment iyup-ping-agent
kubectl rollout restart deployment iyup-api-gateway

# 3. Wait for services to be ready
kubectl rollout status deployment iyup-ping-agent
kubectl rollout status deployment iyup-api-gateway

# 4. Wait 15-30 seconds for Prometheus to scrape new metrics
# Grafana will automatically refresh and show new data
```

**Important Notes:**
- **No need to restart Grafana** - It automatically queries Prometheus for latest data
- **No need to restart Prometheus** - It automatically scrapes the updated services
- **Wait 15-30 seconds** after service restart for Prometheus to scrape and Grafana to refresh
- **Prometheus scrapes every 15 seconds** by default, so new metrics appear quickly

### Verify Latest Data in Grafana

1. **Inspect Raw Prometheus Data (Recommended):**
   
   See the actual data that Grafana queries, not through Grafana UI:
   
   ```bash
   # Port-forward Prometheus first
   kubectl port-forward svc/iyup-prometheus 9090:9090
   
   # Run inspection script (shows all Grafana queries)
   python3 scripts/inspect_prometheus_data.py
   # OR
   ./scripts/inspect_prometheus_data.sh
   ```
   
   This script queries all the same PromQL queries that Grafana uses and shows:
   - Raw metric values
   - Calculated values (rates, increases, percentages)
   - Target health status
   - Any data issues or missing metrics
   
   **This is the best way to verify data correctness before it reaches Grafana!**

2. **Check Prometheus directly:**
   ```bash
   # Port-forward Prometheus
   kubectl port-forward svc/iyup-prometheus 9090:9090
   
   # Query for latest metrics
   curl "http://localhost:9090/api/v1/query?query=ping_success_total"
   
   # Check targets are UP
   open http://localhost:9090/targets
   ```

3. **Check Grafana dashboard:**
   - Port-forward Grafana: `kubectl port-forward svc/iyup-grafana 3000:3000`
   - Open `http://localhost:3000`
   - Refresh the dashboard (or wait for auto-refresh)
   - Check time range is set to "Last 5 minutes" or "Last 1 hour"

4. **Verify new features are working:**
   ```bash
   # Test API gateway with latest code
   curl http://localhost:8080/uptime-summary | jq
   
   # Check ping-agent metrics
   curl http://localhost:18080/metrics | grep ping_success_total
   ```

## Restarting Grafana

If Grafana is already running and you need to restart it:

### Option 1: Rollout Restart (Recommended)

```bash
# Restart Grafana deployment
kubectl rollout restart deployment iyup-grafana

# Wait for it to be ready
kubectl rollout status deployment iyup-grafana
```

This gracefully restarts Grafana while preserving all dashboards and settings (stored in PVC).

### Option 2: Delete Pod (Force Restart)

```bash
# Get the pod name
kubectl get pods -l app.kubernetes.io/component=grafana

# Delete the pod (Kubernetes will automatically recreate it)
kubectl delete pod <grafana-pod-name>
```

### Option 3: Scale Down and Up

```bash
# Scale down to 0
kubectl scale deployment iyup-grafana --replicas=0

# Wait a moment, then scale back up
kubectl scale deployment iyup-grafana --replicas=1

# Check status
kubectl rollout status deployment iyup-grafana
```

### Option 4: Helm Upgrade (If You Changed Config)

```bash
# If you modified Helm values, upgrade the release
helm upgrade iyup ./charts/iyup

# This will restart Grafana if the deployment changed
kubectl rollout status deployment iyup-grafana
```

**Note:** All methods preserve your dashboards and settings since they're stored in a PersistentVolumeClaim (PVC).

## Dashboard Panels

The included dashboard provides:

- **Total API Requests (5m)** → `sum(increase(api_gateway_requests_total[5m]))`
- **Successful Pings** → `ping_success_total`
- **Failed Pings** → `ping_failure_total`
- **Availability %** → `100 * (ping_success_total / (ping_success_total + ping_failure_total))`
- **Requests by Status (rate)** → `sum by (status) (rate(api_gateway_requests_total[1m]))`
- **Ping Success/Failures (rate)** → `rate(ping_success_total[1m])`, `rate(ping_failure_total[1m])`
- **Requests by Path (5m)** → `sum by (path) (increase(api_gateway_requests_total[5m]))`
- **API Latency Histogram** → `sum(rate(api_gateway_request_duration_seconds_bucket[5m])) by (le)`
- **Ping Latency Histogram** → `rate(ping_latency_seconds_bucket[1m])`
- **Average Ping Latency** → `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])`

## Setup Steps

### 1. Port-Forward Grafana

```bash
kubectl port-forward svc/iyup-grafana 3000:3000
```

### 2. Open Grafana

- URL: `http://localhost:3000`
- Default credentials: `admin` / `admin` (Grafana asks you to change them on first login)

### 3. Add Prometheus Data Source

1. Go to **Connections** → **Data sources** → **Add data source**
2. Select **Prometheus**
3. Set URL: `http://iyup-prometheus:9090`
4. Click **Save & Test**

### 4. Import Dashboard

1. Go to **Dashboards** → **New** → **Import**
2. Upload `monitoring/grafana-dashboard.json`
3. Select the Prometheus data source
4. Click **Import**

## Dashboard Structure

### Key Fields

- `title` - Dashboard title
- `refresh` - Auto-refresh interval
- `panels` - Array of panel definitions
- `targets` - PromQL queries for each panel
- `gridPos` - Panel position and size

### Panel Types

- **Stat** - Single value display (uptime %, total requests)
- **Time Series** - Line graphs (rates, trends)
- **Heatmap** - Latency histograms
- **Table** - Tabular data (optional)

## Metrics Cheat Sheet

### Counters

- `ping_success_total{target="..."}` - Total successful pings per target
- `ping_failure_total{target="..."}` - Total failed pings per target
- `api_gateway_requests_total{method="...", path="...", status="..."}` - Total API requests

### Histograms

- `ping_latency_seconds_bucket{target="...", le="..."}` - Latency buckets
- `api_gateway_request_duration_seconds_bucket{method="...", path="...", le="..."}` - API latency buckets

### Rate Queries

```promql
# Success rate
rate(ping_success_total[1m])

# Failure rate
rate(ping_failure_total[1m])

# Average latency
rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])
```

## Prometheus Storage

### Retention

- Default: `14d` (configurable in `charts/iyup/templates/prometheus-deployment.yaml`)
- PVC size: `5Gi` (configurable in `charts/iyup/templates/prometheus-pvc.yaml`)

### Sizing

After 24h of scraping, check:

```promql
prometheus_tsdb_head_series
prometheus_tsdb_head_chunks
rate(prometheus_tsdb_head_samples_appended_total[5m])
```

Or use the sizing script:

```bash
scripts/prometheus-sizing.sh
```

### Disk Usage

Check from inside the pod:

```bash
kubectl exec -it deploy/iyup-prometheus -- du -sh /prometheus
```

## Grafana Cloud Integration

Grafana Cloud does not scrape a Fly app directly. You need a scraper (Grafana Alloy or Prometheus) to pull `/metrics` and `remote_write` to Grafana Cloud.

### Quick Local Alloy Setup (Docker)

1. Create `alloy.hcl`:

```hcl
prometheus.scrape "ping_agent" {
  targets = [{
    __address__ = "iyup-ping-agent.fly.dev",
  }]
  scheme = "https"
  metrics_path = "/metrics"

  forward_to = [prometheus.remote_write.metrics_hosted_prometheus.receiver]
}

prometheus.remote_write "metrics_hosted_prometheus" {
  endpoint {
    name = "hosted-prometheus"
    url  = "https://prometheus-prod-52-prod-ap-southeast-2.grafana.net/api/prom/push"

    basic_auth {
      username = "YOUR_USERNAME"
      password = "YOUR_API_KEY"
    }
  }
}
```

2. Run Alloy:

```bash
docker run --rm -v "$PWD/alloy.hcl:/etc/alloy/config.hcl" grafana/alloy:latest run /etc/alloy/config.hcl
```

### Fly Alloy Scraper

For always-on scraping from Fly, use the config under `monitoring/alloy-fly/`:

- `monitoring/alloy-fly/alloy.hcl` - Fly app config
- `monitoring/alloy-fly/fly.toml` - Fly app definition

Typical flow:

1. Create the app: `fly apps create iyup-alloy`
2. Set secrets: `fly secrets set GRAFANA_USER=... GRAFANA_API_KEY=...`
3. Deploy: `fly deploy` (from `monitoring/alloy-fly/`)

**Security Note:** Keep tokens out of git. Treat anything shown in a screenshot as compromised.

## Persistence

Grafana dashboards and user settings are stored in a PVC (`grafana-pvc`), so they persist across restarts. If you redeploy the Pods, your dashboards and settings should remain.

## Troubleshooting

### Panels Go Blank

Grafana panels may go blank briefly during Prometheus rollouts. Give it ~30 seconds.

### No Data

1. Check Prometheus targets: `http://localhost:9090/targets`
2. Verify data source URL: `http://iyup-prometheus:9090`
3. Check time range in Grafana (top right)
4. Verify metrics exist: `curl http://localhost:9090/api/v1/query?query=ping_success_total`

### Grafana Won't Start

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/component=grafana

# Check pod logs
kubectl logs -l app.kubernetes.io/component=grafana

# Check PVC status
kubectl get pvc | grep grafana

# Check events
kubectl get events --sort-by='.lastTimestamp' | grep grafana
```

### Not Seeing Latest Metrics

If Grafana isn't showing the latest data after code updates:

1. **Verify services are restarted:**
   ```bash
   kubectl get pods -l app.kubernetes.io/component=ping-agent
   kubectl get pods -l app.kubernetes.io/component=api-gateway
   ```

2. **Check Prometheus is scraping:**
   ```bash
   # Port-forward Prometheus
   kubectl port-forward svc/iyup-prometheus 9090:9090
   
   # Check targets are UP
   open http://localhost:9090/targets
   ```

3. **Wait for scrape cycle:**
   - Prometheus scrapes every 15 seconds
   - Wait 30-60 seconds after service restart
   - Refresh Grafana dashboard

4. **Check time range:**
   - Make sure Grafana time range includes "now"
   - Try "Last 5 minutes" or "Last 1 hour"

## Inspecting Raw Prometheus Data

To see the actual data that Grafana queries (not through Grafana UI), use the inspection script:

```bash
# Port-forward Prometheus first
kubectl port-forward svc/iyup-prometheus 9090:9090

# Run inspection (shows all Grafana queries and their results)
python3 scripts/inspect_prometheus_data.py
# OR
./scripts/inspect_prometheus_data.sh
```

This script:
- ✅ Queries all the same PromQL queries that Grafana uses
- ✅ Shows raw metric values and calculated values
- ✅ Checks target health status
- ✅ Identifies missing metrics or data issues
- ✅ Displays results in a readable format

**Use this to verify data correctness before it reaches Grafana!**

### Manual Prometheus Queries

You can also query Prometheus directly:

```bash
# Query a specific metric
curl "http://localhost:9090/api/v1/query?query=ping_success_total"

# Query with time range
curl "http://localhost:9090/api/v1/query_range?query=rate(ping_success_total[1m])&start=$(date -d '5 minutes ago' +%s)&end=$(date +%s)&step=15"

# Use Prometheus UI
open http://localhost:9090/graph
```

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started
- [Deployment Guide](DEPLOYMENT.md) - Prometheus and Grafana configuration
- [Architecture](ARCHITECTURE.md) - Understanding the metrics flow
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
