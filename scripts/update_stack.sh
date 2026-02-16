#!/bin/bash
# Quick script to update iYup stack with latest codebase
# Usage: ./scripts/update_stack.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🔄 Updating iYup stack with latest codebase..."
echo ""

# Check if using Minikube
if kubectl config current-context 2>/dev/null | grep -q minikube; then
    echo "📦 Pointing Docker at Minikube..."
    eval $(minikube -p minikube docker-env)
fi

# Rebuild images
echo "🔨 Rebuilding images with latest code..."
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
echo "✅ Images rebuilt"
echo ""

# Restart deployments
echo "🚀 Restarting deployments..."
kubectl rollout restart deployment iyup-ping-agent
kubectl rollout restart deployment iyup-api-gateway
echo "✅ Deployments restarted"
echo ""

# Wait for readiness
echo "⏳ Waiting for services to be ready..."
kubectl rollout status deployment iyup-ping-agent --timeout=60s
kubectl rollout status deployment iyup-api-gateway --timeout=60s
echo "✅ Services are ready"
echo ""

echo "📊 Waiting 30 seconds for Prometheus to scrape new metrics..."
echo "   (Prometheus scrapes every 15 seconds)"
sleep 30

echo ""
echo "✅ Update complete!"
echo ""
echo "Grafana will automatically show the latest data."
echo "Prometheus scrapes every 15 seconds, so new metrics appear quickly."
echo ""
echo "To verify:"
echo "  kubectl port-forward svc/iyup-grafana 3000:3000"
echo "  open http://localhost:3000"
echo ""
echo "To check metrics directly:"
echo "  kubectl port-forward svc/iyup-prometheus 9090:9090"
echo "  open http://localhost:9090/targets"
