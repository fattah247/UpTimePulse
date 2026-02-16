#!/usr/bin/env python3
"""
Inspect raw Prometheus data that Grafana queries.
This shows the actual data being sent to Grafana, not through Grafana UI.

Usage:
    python3 scripts/inspect_prometheus_data.py [prometheus_url]
"""

import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

PROMETHEUS_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9090"


def query_prometheus(query: str, description: str) -> None:
    """Query Prometheus and display results in a readable format."""
    print("=" * 80)
    print(f"📊 {description}")
    print(f"Query: {query}")
    print()
    
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            print(f"❌ Query failed: {data.get('error', 'Unknown error')}")
            print()
            return
        
        result_type = data.get("data", {}).get("resultType", "")
        results = data.get("data", {}).get("result", [])
        
        if len(results) == 0:
            print("⚠️  No data returned (metric may not exist yet)")
            print()
            return
        
        if result_type == "vector":
            # Instant query - show current values
            for r in results:
                metric = r.get("metric", {})
                value = r.get("value", [])
                if len(value) == 2:
                    timestamp = float(value[0])
                    val = value[1]
                    labels = ", ".join([f'{k}="{v}"' for k, v in metric.items()])
                    dt = datetime.fromtimestamp(timestamp)
                    print(f"  {labels}")
                    print(f"    {dt.strftime('%Y-%m-%d %H:%M:%S')} = {val}")
            print(f"\nTotal: {len(results)} time series")
        
        elif result_type == "matrix":
            # Range query - show time series
            for r in results:
                metric = r.get("metric", {})
                values = r.get("values", [])
                labels = ", ".join([f'{k}="{v}"' for k, v in metric.items()])
                print(f"  {labels}:")
                if len(values) > 0:
                    # Show first 3 and last 3 points
                    for i, (ts, val) in enumerate(values):
                        if i < 3 or i >= len(values) - 3:
                            dt = datetime.fromtimestamp(float(ts))
                            print(f"    {dt.strftime('%H:%M:%S')} = {val}")
                        elif i == 3:
                            print(f"    ... ({len(values) - 6} more points) ...")
                    print(f"    Total points: {len(values)}")
                print()
            print(f"Total: {len(results)} time series")
        
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error querying Prometheus: {e}")
        print()
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print()


def check_targets() -> None:
    """Check Prometheus target health."""
    print("=" * 80)
    print("🎯 Checking Prometheus Targets")
    print()
    
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "success":
            print(f"❌ Failed to get targets: {data.get('error', 'Unknown error')}")
            print()
            return
        
        targets = data.get("data", {}).get("activeTargets", [])
        print("Active Targets:")
        for t in targets:
            labels = t.get("labels", {})
            job = labels.get("job", "unknown")
            health = t.get("health", "unknown")
            last_error = t.get("lastError", "")
            last_scrape = t.get("lastScrape", "")
            scrape_duration = t.get("scrapeDuration", 0)
            
            status = "✅" if health == "up" else "❌"
            print(f"  {status} {job}: {health}")
            if last_error:
                print(f"     Error: {last_error}")
            if last_scrape:
                print(f"     Last scrape: {last_scrape}")
            if scrape_duration:
                print(f"     Scrape duration: {scrape_duration}s")
        print()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking targets: {e}")
        print()


def main():
    """Main inspection routine."""
    print("🔍 Inspecting Prometheus Data (what Grafana queries)")
    print(f"Prometheus URL: {PROMETHEUS_URL}")
    print()
    
    # Check if Prometheus is reachable
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/status/config", timeout=5)
        response.raise_for_status()
        print("✅ Prometheus is reachable")
        print()
    except requests.exceptions.RequestException:
        print(f"❌ Error: Cannot reach Prometheus at {PROMETHEUS_URL}")
        print("   Make sure Prometheus is running and port-forwarded:")
        print("   kubectl port-forward svc/iyup-prometheus 9090:9090")
        sys.exit(1)
    
    # Check targets
    check_targets()
    
    # Key metrics that Grafana queries (from grafana-dashboard.json)
    
    # 1. Ping metrics
    query_prometheus(
        "ping_success_total",
        "Ping Success Counter (raw)"
    )
    
    query_prometheus(
        "ping_failure_total",
        "Ping Failure Counter (raw)"
    )
    
    query_prometheus(
        'sum(increase(ping_success_total{target="https://google.com"}[5m]))',
        "Successful Pings (5m) - google.com (Grafana Panel)"
    )
    
    query_prometheus(
        'sum(increase(ping_success_total{target="https://github.com"}[5m]))',
        "Successful Pings (5m) - github.com (Grafana Panel)"
    )
    
    query_prometheus(
        'sum(increase(ping_failure_total{target="https://google.com"}[5m]))',
        "Failed Pings (5m) - google.com (Grafana Panel)"
    )
    
    query_prometheus(
        '100 * increase(ping_success_total{target="https://google.com"}[5m]) / clamp_min(increase(ping_success_total{target="https://google.com"}[5m]) + increase(ping_failure_total{target="https://google.com"}[5m]), 1)',
        "Availability % (5m) - google.com (Grafana Panel)"
    )
    
    query_prometheus(
        'rate(ping_success_total{target="https://google.com"}[1m])',
        "Ping Success Rate (1m) - google.com (Grafana Panel)"
    )
    
    query_prometheus(
        'rate(ping_failure_total{target="https://google.com"}[1m])',
        "Ping Failure Rate (1m) - google.com (Grafana Panel)"
    )
    
    # 2. Latency metrics
    query_prometheus(
        'ping_latency_seconds_bucket{target="https://google.com"}',
        "Ping Latency Histogram Buckets - google.com (raw)"
    )
    
    query_prometheus(
        'sum(rate(ping_latency_seconds_sum{target="https://google.com"}[1m])) / clamp_min(sum(rate(ping_latency_seconds_count{target="https://google.com"}[1m])), 1)',
        "Average Ping Latency (1m) - google.com (Grafana Panel)"
    )
    
    query_prometheus(
        'histogram_quantile(0.95, sum by (le) (rate(ping_latency_seconds_bucket{target="https://google.com"}[5m])))',
        "Ping Latency p95 (5m) - google.com (Grafana Panel)"
    )
    
    # 3. API Gateway metrics
    query_prometheus(
        "api_gateway_requests_total",
        "API Gateway Requests Counter (raw)"
    )
    
    query_prometheus(
        "sum(increase(api_gateway_requests_total[5m]))",
        "Total API Requests (5m) (Grafana Panel)"
    )
    
    query_prometheus(
        'sum by (status) (rate(api_gateway_requests_total[1m]))',
        "Requests by Status (rate) (Grafana Panel)"
    )
    
    query_prometheus(
        'sum by (path) (increase(api_gateway_requests_total[5m]))',
        "Requests by Path (5m) (Grafana Panel)"
    )
    
    query_prometheus(
        'sum(rate(api_gateway_requests_total{status=~"5.."}[5m]))',
        "API 5xx Rate (5m) (Grafana Panel)"
    )
    
    # 4. Scrape health
    query_prometheus(
        'up{job="ping-agent"}',
        "Scrape Up - ping-agent (Grafana Panel)"
    )
    
    query_prometheus(
        'up{job="api-gateway"}',
        "Scrape Up - api-gateway (Grafana Panel)"
    )
    
    query_prometheus(
        'scrape_duration_seconds{job=~"ping-agent|api-gateway"}',
        "Scrape Duration (Grafana Panel)"
    )
    
    # 5. Alerts
    query_prometheus(
        'sum(ALERTS{alertstate="firing"})',
        "Alerts Firing (Grafana Panel)"
    )
    
    print("=" * 80)
    print("✅ Inspection complete!")
    print()
    print("💡 Tips:")
    print("   - If you see 'No data returned', the metric may not exist yet")
    print("   - Wait 15-30 seconds after service restart for Prometheus to scrape")
    print(f"   - Check targets are UP: {PROMETHEUS_URL}/targets")
    print(f"   - View raw metrics: {PROMETHEUS_URL}/graph")
    print()


if __name__ == "__main__":
    main()
