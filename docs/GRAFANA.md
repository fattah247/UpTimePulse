# Grafana Dashboard Setup

Complete guide to setting up and using Grafana dashboards with iYup.

## Overview

Grafana dashboards are JSON documents that define panels, queries, and visualizations. The iYup project includes a pre-configured dashboard at `monitoring/grafana-dashboard.json`.

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
- Default credentials: `admin` / `admin` (Grafana will prompt to change on first login)

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

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started
- [Deployment Guide](DEPLOYMENT.md) - Prometheus and Grafana configuration
- [Architecture](ARCHITECTURE.md) - Understanding the metrics flow
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
