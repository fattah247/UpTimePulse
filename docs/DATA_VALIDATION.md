# Data Validation Guide

How to validate Prometheus data quality and ensure Grafana displays correct values.

## Quick Start

```bash
# 1. Port-forward Prometheus
kubectl port-forward svc/iyup-prometheus 9090:9090

# 2. Run validation (iterative - fixes issues automatically)
./scripts/validate_and_fix.sh

# OR run validation once
python3 scripts/validate_prometheus_data.py
```

## What Gets Validated

The validation script checks:

### 1. Target Health
- ✅ Prometheus targets are UP (ping-agent, api-gateway)
- ✅ No scrape errors
- ✅ Targets are being scraped regularly

### 2. Counter Metrics
- ✅ `ping_success_total` exists for all targets
- ✅ `ping_failure_total` exists for all targets
- ✅ Counter values are non-negative
- ✅ All expected targets have metrics

### 3. Data Consistency
- ✅ Success + failure counts are consistent
- ✅ Availability calculations are correct (0-100%)
- ✅ No suspicious patterns (e.g., 100% failures)

### 4. Latency Metrics
- ✅ Latency histograms exist
- ✅ Average latency is reasonable (< 60s)
- ✅ No negative latency values

### 5. API Gateway Metrics
- ✅ Request counters exist
- ✅ Error rates are acceptable
- ✅ Metrics are being recorded

### 6. Grafana Query Validation
- ✅ All Grafana panel queries return valid data
- ✅ Calculations match expected formulas
- ✅ Time ranges have data

## Validation Scripts

### `validate_prometheus_data.py`

Comprehensive validation script that checks all aspects of data quality.

**Usage:**
```bash
python3 scripts/validate_prometheus_data.py [prometheus_url]
```

**Output:**
- ✅ Green checkmarks for valid data
- ❌ Red X for errors
- ⚠️ Yellow warnings for potential issues

**Exit Codes:**
- `0` - All validations passed
- `1` - Errors or warnings found

### `validate_and_fix.sh`

Iterative validation script that:
1. Runs validation
2. Automatically fixes common issues (restarts services if needed)
3. Re-validates
4. Repeats until all checks pass (max 10 iterations)

**Usage:**
```bash
./scripts/validate_and_fix.sh [prometheus_url]
```

**What it fixes:**
- Restarts services if they're not ready
- Waits for Prometheus to scrape new metrics
- Re-runs validation after fixes

### `inspect_prometheus_data.py`

Shows the actual raw data that Grafana queries (for debugging).

**Usage:**
```bash
python3 scripts/inspect_prometheus_data.py [prometheus_url]
```

## Common Issues and Fixes

### Issue: "No data for ping_success_total"

**Cause:** Metrics haven't been scraped yet or ping-agent isn't running.

**Fix:**
```bash
# Check if ping-agent is running
kubectl get pods -l app.kubernetes.io/component=ping-agent

# Restart if needed
kubectl rollout restart deployment iyup-ping-agent
kubectl rollout status deployment iyup-ping-agent

# Wait 30 seconds for Prometheus to scrape
sleep 30
```

### Issue: "Target ping-agent is down"

**Cause:** Prometheus can't scrape the ping-agent endpoint.

**Fix:**
```bash
# Check target status in Prometheus UI
open http://localhost:9090/targets

# Check ping-agent logs
kubectl logs -l app.kubernetes.io/component=ping-agent

# Verify service is accessible
kubectl port-forward svc/iyup-ping-agent 18080:8080
curl http://localhost:18080/metrics
```

### Issue: "Negative counter value"

**Cause:** Counter was reset or corrupted (should never happen with Prometheus counters).

**Fix:**
```bash
# Restart the service to reset metrics
kubectl rollout restart deployment iyup-ping-agent

# Wait for new metrics
sleep 30
```

### Issue: "High failure rate"

**Cause:** Targets are actually down or network issues.

**Fix:**
```bash
# Check if targets are actually reachable
curl -I https://google.com
curl -I https://github.com

# Check ping-agent logs for errors
kubectl logs -l app.kubernetes.io/component=ping-agent --tail=50
```

### Issue: "Invalid availability value (> 100%)"

**Cause:** Calculation error in PromQL query.

**Fix:** This is a code issue. Check the Grafana dashboard queries in `monitoring/grafana-dashboard.json`.

## Validation Workflow

### After Code Changes

1. **Update stack with latest code:**
   ```bash
   ./scripts/update_stack.sh
   ```

2. **Run validation:**
   ```bash
   kubectl port-forward svc/iyup-prometheus 9090:9090
   ./scripts/validate_and_fix.sh
   ```

3. **Verify in Grafana:**
   ```bash
   kubectl port-forward svc/iyup-grafana 3000:3000
   open http://localhost:3000
   ```

### Continuous Validation

Run validation periodically to catch data quality issues:

```bash
# Run validation every 5 minutes
watch -n 300 'python3 scripts/validate_prometheus_data.py'
```

## Integration with CI/CD

Add validation to your deployment pipeline:

```yaml
# Example GitHub Actions step
- name: Validate Prometheus Data
  run: |
    kubectl port-forward svc/iyup-prometheus 9090:9090 &
    sleep 10
    python3 scripts/validate_prometheus_data.py http://localhost:9090
```

## Related Documentation

- [Grafana Setup](GRAFANA.md) - Setting up dashboards
- [Deployment Guide](DEPLOYMENT.md) - Updating services
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
