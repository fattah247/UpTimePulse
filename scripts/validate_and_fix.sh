#!/bin/bash
# Iteratively validate Prometheus data, fix issues, and re-validate until clean
# Usage: ./scripts/validate_and_fix.sh [prometheus_url]

set -e

PROMETHEUS_URL="${1:-http://localhost:9090}"
MAX_ITERATIONS=10
ITERATION=0

echo "🔄 Starting iterative data validation and fixing process"
echo "Prometheus URL: $PROMETHEUS_URL"
echo ""

# Check if Prometheus is accessible
check_prometheus() {
    if ! curl -s -f "${PROMETHEUS_URL}/api/v1/status/config" > /dev/null 2>&1; then
        echo "❌ Cannot reach Prometheus at $PROMETHEUS_URL"
        echo ""
        echo "Please ensure:"
        echo "  1. Prometheus is running in Kubernetes"
        echo "  2. Port-forward is active: kubectl port-forward svc/iyup-prometheus 9090:9090"
        echo ""
        exit 1
    fi
}

# Run validation
run_validation() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Iteration $ITERATION: Running validation..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python3 scripts/validate_prometheus_data.py "$PROMETHEUS_URL"
    return $?
}

# Fix common issues
fix_issues() {
    echo ""
    echo "🔧 Attempting to fix issues..."
    echo ""
    
    # Check if services need restart
    echo "Checking service status..."
    if command -v kubectl > /dev/null 2>&1; then
        # Check if pods are running
        PING_AGENT_READY=$(kubectl get pods -l app.kubernetes.io/component=ping-agent -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        API_GATEWAY_READY=$(kubectl get pods -l app.kubernetes.io/component=api-gateway -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [ "$PING_AGENT_READY" != "True" ] || [ "$API_GATEWAY_READY" != "True" ]; then
            echo "⚠️  Some services are not ready. Restarting..."
            kubectl rollout restart deployment iyup-ping-agent 2>/dev/null || true
            kubectl rollout restart deployment iyup-api-gateway 2>/dev/null || true
            echo "⏳ Waiting for services to be ready..."
            kubectl rollout status deployment iyup-ping-agent --timeout=60s 2>/dev/null || true
            kubectl rollout status deployment iyup-api-gateway --timeout=60s 2>/dev/null || true
            echo "✅ Services restarted. Waiting 30s for Prometheus to scrape..."
            sleep 30
        else
            echo "✅ All services are ready"
        fi
    else
        echo "⚠️  kubectl not found - cannot check/restart services automatically"
    fi
}

# Main loop
main() {
    check_prometheus
    
    while [ $ITERATION -lt $MAX_ITERATIONS ]; do
        ITERATION=$((ITERATION + 1))
        
        if run_validation; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "✅ SUCCESS! All data validations passed after $ITERATION iteration(s)"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "Data quality is good. Grafana should display correct values."
            exit 0
        fi
        
        if [ $ITERATION -ge $MAX_ITERATIONS ]; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "❌ Reached maximum iterations ($MAX_ITERATIONS)"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "Please review the errors above and fix them manually."
            exit 1
        fi
        
        fix_issues
        
        echo ""
        echo "🔄 Re-running validation in 5 seconds..."
        sleep 5
        echo ""
    done
}

main
