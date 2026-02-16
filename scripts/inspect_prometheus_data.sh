#!/bin/bash
# Inspect raw Prometheus data that Grafana queries
# This shows the actual data being sent to Grafana, not through Grafana UI
# Usage: ./scripts/inspect_prometheus_data.sh [prometheus_url]

set -e

PROMETHEUS_URL="${1:-http://localhost:9090}"

echo "🔍 Inspecting Prometheus Data (what Grafana queries)"
echo "Prometheus URL: $PROMETHEUS_URL"
echo ""

# Check if Prometheus is reachable
if ! curl -s -f "${PROMETHEUS_URL}/api/v1/status/config" > /dev/null 2>&1; then
    echo "❌ Error: Cannot reach Prometheus at $PROMETHEUS_URL"
    echo "   Make sure Prometheus is running and port-forwarded:"
    echo "   kubectl port-forward svc/iyup-prometheus 9090:9090"
    exit 1
fi

echo "✅ Prometheus is reachable"
echo ""

# Function to query Prometheus
query_prometheus() {
    local query="$1"
    local description="$2"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 $description"
    echo "Query: $query"
    echo ""
    
    local response=$(curl -s -G "${PROMETHEUS_URL}/api/v1/query" --data-urlencode "query=${query}")
    
    # Check if query was successful
    local status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$status" != "success" ]; then
        echo "❌ Query failed!"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        echo ""
        return 1
    fi
    
    # Extract results
    local result_type=$(echo "$response" | grep -o '"resultType":"[^"]*"' | cut -d'"' -f4)
    local result_count=$(echo "$response" | grep -o '"result":\[' | wc -l)
    
    if [ "$result_type" = "vector" ]; then
        # Vector result - show each metric
        echo "$response" | python3 -c "
import json
import sys
data = json.load(sys.stdin)
if 'data' in data and 'result' in data['data']:
    results = data['data']['result']
    if len(results) == 0:
        print('⚠️  No data returned (metric may not exist yet)')
    else:
        for r in results:
            metric = r.get('metric', {})
            value = r.get('value', [])
            if len(value) == 2:
                timestamp = value[0]
                val = value[1]
                labels = ', '.join([f'{k}=\"{v}\"' for k, v in metric.items()])
                print(f'  {labels} = {val}')
        print(f'')
        print(f'Total: {len(results)} time series')
" 2>/dev/null || echo "$response"
    elif [ "$result_type" = "matrix" ]; then
        # Matrix result - show sample points
        echo "$response" | python3 -c "
import json
import sys
from datetime import datetime
data = json.load(sys.stdin)
if 'data' in data and 'result' in data['data']:
    results = data['data']['result']
    if len(results) == 0:
        print('⚠️  No data returned (metric may not exist yet)')
    else:
        for r in results:
            metric = r.get('metric', {})
            values = r.get('values', [])
            labels = ', '.join([f'{k}=\"{v}\"' for k, v in metric.items()])
            print(f'  {labels}:')
            if len(values) > 0:
                # Show first and last 3 points
                for i, (ts, val) in enumerate(values):
                    if i < 3 or i >= len(values) - 3:
                        dt = datetime.fromtimestamp(float(ts))
                        print(f'    {dt.strftime(\"%H:%M:%S\")} = {val}')
                    elif i == 3:
                        print(f'    ... ({len(values) - 6} more points) ...')
                print(f'    Total points: {len(values)}')
            print('')
        print(f'Total: {len(results)} time series')
" 2>/dev/null || echo "$response"
    else
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    fi
    
    echo ""
}

# Check if targets are up
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Checking Prometheus Targets"
echo ""

targets_response=$(curl -s "${PROMETHEUS_URL}/api/v1/targets")
echo "$targets_response" | python3 -c "
import json
import sys
data = json.load(sys.stdin)
if 'data' in data and 'activeTargets' in data['data']:
    targets = data['data']['activeTargets']
    print('Active Targets:')
    for t in targets:
        job = t.get('labels', {}).get('job', 'unknown')
        health = t.get('health', 'unknown')
        last_error = t.get('lastError', '')
        last_scrape = t.get('lastScrape', '')
        scrape_duration = t.get('scrapeDuration', 0)
        status = '✅' if health == 'up' else '❌'
        print(f'  {status} {job}: {health}')
        if last_error:
            print(f'     Error: {last_error}')
        if last_scrape:
            print(f'     Last scrape: {last_scrape}')
        if scrape_duration:
            print(f'     Scrape duration: {scrape_duration}s')
    print('')
" 2>/dev/null || echo "$targets_response"

echo ""

# Key metrics that Grafana queries (from grafana-dashboard.json)

# 1. Ping metrics
query_prometheus \
    'ping_success_total' \
    "Ping Success Counter (raw)"

query_prometheus \
    'ping_failure_total' \
    "Ping Failure Counter (raw)"

query_prometheus \
    'sum(increase(ping_success_total{target="https://google.com"}[5m]))' \
    "Successful Pings (5m) - google.com (Grafana Panel)"

query_prometheus \
    'sum(increase(ping_success_total{target="https://github.com"}[5m]))' \
    "Successful Pings (5m) - github.com (Grafana Panel)"

query_prometheus \
    'sum(increase(ping_failure_total{target="https://google.com"}[5m]))' \
    "Failed Pings (5m) - google.com (Grafana Panel)"

query_prometheus \
    '100 * increase(ping_success_total{target="https://google.com"}[5m]) / clamp_min(increase(ping_success_total{target="https://google.com"}[5m]) + increase(ping_failure_total{target="https://google.com"}[5m]), 1)' \
    "Availability % (5m) - google.com (Grafana Panel)"

query_prometheus \
    'rate(ping_success_total{target="https://google.com"}[1m])' \
    "Ping Success Rate (1m) - google.com (Grafana Panel)"

query_prometheus \
    'rate(ping_failure_total{target="https://google.com"}[1m])' \
    "Ping Failure Rate (1m) - google.com (Grafana Panel)"

# 2. Latency metrics
query_prometheus \
    'ping_latency_seconds_bucket{target="https://google.com"}' \
    "Ping Latency Histogram Buckets - google.com (raw)"

query_prometheus \
    'sum(rate(ping_latency_seconds_sum{target="https://google.com"}[1m])) / clamp_min(sum(rate(ping_latency_seconds_count{target="https://google.com"}[1m])), 1)' \
    "Average Ping Latency (1m) - google.com (Grafana Panel)"

query_prometheus \
    'histogram_quantile(0.95, sum by (le) (rate(ping_latency_seconds_bucket{target="https://google.com"}[5m])))' \
    "Ping Latency p95 (5m) - google.com (Grafana Panel)"

# 3. API Gateway metrics
query_prometheus \
    'api_gateway_requests_total' \
    "API Gateway Requests Counter (raw)"

query_prometheus \
    'sum(increase(api_gateway_requests_total[5m]))' \
    "Total API Requests (5m) (Grafana Panel)"

query_prometheus \
    'sum by (status) (rate(api_gateway_requests_total[1m]))' \
    "Requests by Status (rate) (Grafana Panel)"

query_prometheus \
    'sum by (path) (increase(api_gateway_requests_total[5m]))' \
    "Requests by Path (5m) (Grafana Panel)"

query_prometheus \
    'sum(rate(api_gateway_requests_total{status=~"5.."}[5m]))' \
    "API 5xx Rate (5m) (Grafana Panel)"

# 4. Scrape health
query_prometheus \
    'up{job="ping-agent"}' \
    "Scrape Up - ping-agent (Grafana Panel)"

query_prometheus \
    'up{job="api-gateway"}' \
    "Scrape Up - api-gateway (Grafana Panel)"

query_prometheus \
    'scrape_duration_seconds{job=~"ping-agent|api-gateway"}' \
    "Scrape Duration (Grafana Panel)"

# 5. Alerts
query_prometheus \
    'sum(ALERTS{alertstate="firing"})' \
    "Alerts Firing (Grafana Panel)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Inspection complete!"
echo ""
echo "💡 Tips:"
echo "   - If you see 'No data returned', the metric may not exist yet"
echo "   - Wait 15-30 seconds after service restart for Prometheus to scrape"
echo "   - Check targets are UP: ${PROMETHEUS_URL}/targets"
echo "   - View raw metrics: ${PROMETHEUS_URL}/graph"
echo ""
