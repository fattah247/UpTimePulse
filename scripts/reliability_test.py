#!/usr/bin/env python3
"""
Long-running reliability test for iYup services.
Tests ping-agent and api-gateway for at least 2 hours to ensure reliability.
"""

import json
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configuration
TEST_DURATION_HOURS = 2.0
CHECK_INTERVAL_SECONDS = 30
TARGETS = ["https://google.com", "https://github.com"]
PING_AGENT_PORT = 18080
API_GATEWAY_PORT = 18081

# Statistics tracking
stats = {
    "start_time": None,
    "end_time": None,
    "checks_performed": 0,
    "api_gateway_checks": defaultdict(int),
    "ping_agent_checks": defaultdict(int),
    "errors": [],
    "uptime_data": defaultdict(list),
    "latency_data": defaultdict(list),
}


def log(message: str, level: str = "INFO"):
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def check_service_health(url: str, service_name: str) -> bool:
    """Check if a service is healthy."""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            stats[f"{service_name}_checks"]["success"] += 1
            return True
        else:
            stats[f"{service_name}_checks"]["http_error"] += 1
            stats["errors"].append(
                f"{service_name} returned status {response.status_code}"
            )
            return False
    except requests.RequestException as e:
        stats[f"{service_name}_checks"]["connection_error"] += 1
        stats["errors"].append(f"{service_name} connection error: {e}")
        return False


def check_ping_agent_metrics() -> Optional[Dict]:
    """Fetch and parse ping-agent metrics."""
    try:
        url = f"http://localhost:{PING_AGENT_PORT}/metrics"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        metrics_text = response.text
        results = {}
        
        for line in metrics_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Parse ping_success_total and ping_failure_total
            for metric_name in ["ping_success_total", "ping_failure_total"]:
                if metric_name in line and 'target=' in line:
                    try:
                        # Extract target and value
                        if '{' in line and '}' in line:
                            target_start = line.find('target="') + 8
                            target_end = line.find('"', target_start)
                            target = line[target_start:target_end]
                            
                            value_start = line.rfind(' ') + 1
                            value = float(line[value_start:])
                            
                            if target not in results:
                                results[target] = {"success": 0.0, "failures": 0.0}
                            
                            if "success" in metric_name:
                                results[target]["success"] = value
                            elif "failure" in metric_name:
                                results[target]["failures"] = value
                    except (ValueError, IndexError):
                        continue
        
        return results
    except requests.RequestException as e:
        stats["errors"].append(f"Failed to fetch ping-agent metrics: {e}")
        return None


def check_api_gateway_uptime_summary() -> Optional[Dict]:
    """Fetch uptime summary from api-gateway."""
    try:
        url = f"http://localhost:{API_GATEWAY_PORT}/uptime-summary"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        stats["errors"].append(f"Failed to fetch uptime-summary: {e}")
        return None


def check_api_gateway_targets() -> Optional[Dict]:
    """Fetch targets from api-gateway."""
    try:
        url = f"http://localhost:{API_GATEWAY_PORT}/targets"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        stats["errors"].append(f"Failed to fetch targets: {e}")
        return None


def validate_uptime_data(uptime_data: Dict, ping_metrics: Optional[Dict]) -> List[str]:
    """Validate that uptime data is consistent and correct."""
    issues = []
    
    if not uptime_data or "targets" not in uptime_data:
        issues.append("uptime-summary missing 'targets' key")
        return issues
    
    targets = uptime_data["targets"]
    
    # Check all expected targets are present
    target_urls = {t["url"] for t in targets}
    for expected_target in TARGETS:
        if expected_target not in target_urls:
            issues.append(f"Missing expected target: {expected_target}")
    
    # Validate each target's data
    for target_info in targets:
        url = target_info.get("url")
        success = target_info.get("success", 0)
        failures = target_info.get("failures", 0)
        availability = target_info.get("availability", "0%")
        
        if not url:
            issues.append("Target missing URL")
            continue
        
        # Check availability calculation
        total = success + failures
        if total > 0:
            expected_avail = (success / total) * 100
            # Parse availability string (e.g., "99%")
            try:
                actual_avail = float(availability.rstrip("%"))
                if abs(actual_avail - expected_avail) > 1.0:  # Allow 1% tolerance
                    issues.append(
                        f"{url}: Availability mismatch: {actual_avail}% vs {expected_avail:.1f}%"
                    )
            except ValueError:
                issues.append(f"{url}: Invalid availability format: {availability}")
        
        # Cross-check with ping-agent metrics if available
        if ping_metrics and url in ping_metrics:
            ping_success = ping_metrics[url].get("success", 0)
            ping_failures = ping_metrics[url].get("failures", 0)
            
            # Allow small differences due to timing
            if abs(ping_success - success) > 5 or abs(ping_failures - failures) > 5:
                issues.append(
                    f"{url}: Metrics mismatch - API: {success}/{failures}, Ping: {ping_success}/{ping_failures}"
                )
    
    return issues


def run_reliability_test():
    """Run the long-running reliability test."""
    log(f"Starting reliability test for {TEST_DURATION_HOURS} hours")
    log(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    log(f"Targets: {', '.join(TARGETS)}")
    
    stats["start_time"] = datetime.now()
    end_time = stats["start_time"] + timedelta(hours=TEST_DURATION_HOURS)
    
    log(f"Test will run until: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    try:
        while datetime.now() < end_time:
            check_start = time.time()
            stats["checks_performed"] += 1
            
            log(f"Check #{stats['checks_performed']} starting...")
            
            # Check ping-agent health
            ping_agent_healthy = check_service_health(
                f"http://localhost:{PING_AGENT_PORT}/healthz", "ping_agent"
            )
            
            # Check api-gateway health
            api_gateway_healthy = check_service_health(
                f"http://localhost:{API_GATEWAY_PORT}/healthz", "api_gateway"
            )
            
            if not ping_agent_healthy or not api_gateway_healthy:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    log(
                        f"ERROR: {consecutive_errors} consecutive health check failures. Aborting test.",
                        "ERROR",
                    )
                    break
            else:
                consecutive_errors = 0
            
            # Fetch metrics
            ping_metrics = check_ping_agent_metrics()
            uptime_data = check_api_gateway_uptime_summary()
            targets_data = check_api_gateway_targets()
            
            # Validate data
            if uptime_data:
                issues = validate_uptime_data(uptime_data, ping_metrics)
                if issues:
                    for issue in issues:
                        log(f"Validation issue: {issue}", "WARNING")
                        stats["errors"].append(f"Validation: {issue}")
                else:
                    # Store valid data for analysis
                    for target_info in uptime_data.get("targets", []):
                        url = target_info.get("url")
                        if url:
                            stats["uptime_data"][url].append({
                                "timestamp": datetime.now().isoformat(),
                                "success": target_info.get("success", 0),
                                "failures": target_info.get("failures", 0),
                                "availability": target_info.get("availability", "0%"),
                            })
            
            # Log current status
            if uptime_data:
                log("Current uptime summary:")
                for target_info in uptime_data.get("targets", []):
                    log(
                        f"  {target_info.get('url')}: {target_info.get('availability')} "
                        f"(Success: {target_info.get('success')}, Failures: {target_info.get('failures')})"
                    )
            
            # Calculate sleep time
            check_duration = time.time() - check_start
            sleep_time = max(0, CHECK_INTERVAL_SECONDS - check_duration)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                log(
                    f"WARNING: Check took {check_duration:.2f}s, longer than interval {CHECK_INTERVAL_SECONDS}s",
                    "WARNING",
                )
    
    except KeyboardInterrupt:
        log("Test interrupted by user", "WARNING")
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        stats["errors"].append(f"Unexpected error: {e}")
    
    stats["end_time"] = datetime.now()
    generate_report()


def generate_report():
    """Generate a comprehensive test report."""
    log("\n" + "=" * 80)
    log("RELIABILITY TEST REPORT")
    log("=" * 80)
    
    duration = stats["end_time"] - stats["start_time"]
    log(f"Test Duration: {duration}")
    log(f"Total Checks: {stats['checks_performed']}")
    log(f"Start Time: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"End Time: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    log("\n--- Service Health Checks ---")
    for service in ["ping_agent", "api_gateway"]:
        checks = stats[f"{service}_checks"]
        total = sum(checks.values())
        if total > 0:
            success_rate = (checks.get("success", 0) / total) * 100
            log(f"{service}:")
            log(f"  Total: {total}")
            log(f"  Success: {checks.get('success', 0)} ({success_rate:.1f}%)")
            log(f"  HTTP Errors: {checks.get('http_error', 0)}")
            log(f"  Connection Errors: {checks.get('connection_error', 0)}")
    
    log("\n--- Errors ---")
    if stats["errors"]:
        log(f"Total Errors: {len(stats['errors'])}")
        # Show last 20 errors
        for error in stats["errors"][-20:]:
            log(f"  {error}")
    else:
        log("No errors recorded!")
    
    log("\n--- Uptime Data Summary ---")
    for url, data_points in stats["uptime_data"].items():
        if data_points:
            log(f"\n{url}:")
            log(f"  Data Points: {len(data_points)}")
            
            # Calculate statistics
            availabilities = []
            for point in data_points:
                try:
                    avail = float(point["availability"].rstrip("%"))
                    availabilities.append(avail)
                except (ValueError, KeyError):
                    continue
            
            if availabilities:
                log(f"  Average Availability: {sum(availabilities) / len(availabilities):.2f}%")
                log(f"  Min Availability: {min(availabilities):.2f}%")
                log(f"  Max Availability: {max(availabilities):.2f}%")
    
    # Save detailed report to file
    report_file = Path(__file__).parent.parent / "reliability_test_report.json"
    with open(report_file, "w") as f:
        json.dump(stats, f, indent=2, default=str)
    log(f"\nDetailed report saved to: {report_file}")
    
    log("\n" + "=" * 80)
    
    # Determine overall result
    if len(stats["errors"]) == 0:
        log("RESULT: PASSED - No errors detected", "INFO")
        return 0
    else:
        error_rate = len(stats["errors"]) / stats["checks_performed"] if stats["checks_performed"] > 0 else 1.0
        if error_rate < 0.01:  # Less than 1% error rate
            log(f"RESULT: PASSED - Low error rate ({error_rate*100:.2f}%)", "INFO")
            return 0
        else:
            log(f"RESULT: FAILED - High error rate ({error_rate*100:.2f}%)", "ERROR")
            return 1


if __name__ == "__main__":
    # Check if services are running
    log("Checking if services are running...")
    
    ping_agent_running = False
    api_gateway_running = False
    
    try:
        response = requests.get(f"http://localhost:{PING_AGENT_PORT}/healthz", timeout=2)
        if response.status_code == 200:
            ping_agent_running = True
            log("✓ ping-agent is running")
    except requests.RequestException:
        log("✗ ping-agent is not running. Please start it first.", "ERROR")
    
    try:
        response = requests.get(f"http://localhost:{API_GATEWAY_PORT}/healthz", timeout=2)
        if response.status_code == 200:
            api_gateway_running = True
            log("✓ api-gateway is running")
    except requests.RequestException:
        log("✗ api-gateway is not running. Please start it first.", "ERROR")
    
    if not ping_agent_running or not api_gateway_running:
        log("\nPlease start the services before running the reliability test:")
        log("  cd services/ping-agent && go run main.go &")
        log("  cd services/api-gateway && uvicorn main:app --port 18081 &")
        sys.exit(1)
    
    # Run the test
    sys.exit(run_reliability_test())
