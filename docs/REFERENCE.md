# Command Reference

Quick reference for commands, flags, and cheat sheets used in iYup.

## Command Notes

### Minikube and kubectl

- `minikube start` - Starts a local Kubernetes cluster
- `kubectl config use-context minikube` - Points `kubectl` at that cluster
- `eval $(minikube -p minikube docker-env)` - Points Docker at Minikube's Docker daemon
- `helm install iyup ./charts/iyup` - Installs the chart into the cluster
- `helm upgrade --install iyup ./charts/iyup` - Re-applies chart changes
- `kubectl port-forward svc/iyup-ping-agent 18080:8080` - Tunnels a Service port to your machine

### Docker

- `docker build -t ping-agent:dev .` - Builds and tags an image from the current directory
- `docker run --rm ping-agent:dev` - Runs the image and deletes the container after exit
- `docker ps` - Lists running containers
- `docker ps -a` - Lists all containers, including stopped
- `docker images` - Lists local images
- `docker stop <container>` - Stops a running container

### Curl

- `curl -v http://localhost:18080/metrics` - Sends an HTTP request and shows verbose output
- `curl http://localhost:8080/uptime-summary | jq` - Pretty-print JSON response

## Flag Cheat Sheet

Common flags used in this project:

- `-f` - Read from file (used by `kubectl`)
- `-v` - Verbose output (used by `curl`)
- `-t` - Tag name (used by `docker build`)
- `-p` - Profile name (used by `minikube`)
- `--rm` - Remove container after exit (used by `docker run`)

## Metrics Cheat Sheet

### PromQL Queries

**Counters:**
- `ping_success_total` - Total successful pings (counter)
- `ping_failure_total` - Total failed pings (counter)
- `api_gateway_requests_total` - Total API requests (counter)

**Histograms:**
- `ping_latency_seconds` - Latency histogram
- `api_gateway_request_duration_seconds` - API latency histogram

**Rate Queries:**
```promql
# Success rate
rate(ping_success_total[1m])

# Failure rate
rate(ping_failure_total[1m])

# Average latency
rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])
```

**Increase Queries:**
```promql
# Increase over 5 minutes
increase(ping_success_total[5m])

# Increase by target
sum by (target) (increase(ping_success_total[5m]))
```

### Grafana Panel Types

- `ping_success_total` (counter) → Stat panel
- `ping_failure_total` (counter) → Stat panel
- `ping_latency_seconds` (histogram) → Heatmap/Histogram panel
- `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])` (avg latency) → Line graph

## Kubernetes Resource Types

### ConfigMap
Key/value config mounted into pods (e.g., `prometheus-configmap`).

### Secret
Like a ConfigMap, but for sensitive values (e.g., `alertmanager-secret`).

### PVC (PersistentVolumeClaim)
Storage request for durable data (e.g., Prometheus + Grafana storage).

### HPA (Horizontal Pod Autoscaler)
Scales replicas based on metrics (CPU in this repo).

### Deployment
Manages pod replicas and rollouts for a service.

### Service
Stable DNS + load-balancing over pods.

### Ingress
HTTP entrypoint that routes host/path → Service (needs an Ingress controller).

## Why These Pieces Exist

### Ingress
Ingress is the Kubernetes "front door" for HTTP. It maps a hostname/path to a Service (like `api-gateway`) so you can reach it without port-forwarding. It only works if an Ingress controller (e.g., NGINX) is installed. In this chart, it's off by default (`ingress.enabled: false`).

### HPA
HPA = Horizontal Pod Autoscaler. It automatically scales the number of pod replicas based on metrics (usually CPU). In this chart, the HPA targets `api-gateway` and scales between 1–3 replicas when CPU goes high.

### Metrics Producer (ping-agent)
This is the heart of the system. If this isn't running, everything else is just watching silence. It pings a URL, then exposes:
- counters (`ping_success_total`, `ping_failure_total`)
- histogram (`ping_latency_seconds`)
- `/metrics` for scraping
- targets come from `PING_TARGET_URLS` (single source for ping-agent and api-gateway)

Without this, there's nothing to observe.

### Metrics Collection (Prometheus)
Prometheus pulls `/metrics` every 15s and stores the history. That's the difference between "I can see a number now" and "I can graph the last 24 hours."

## Go Module Files

### go.mod
Declares the module name, the Go version, and direct dependencies.

### go.sum
Records exact checksums so builds are reproducible.

**Important:** If `go.sum` is missing, Docker builds will break — guaranteed.

## Helm Templating

- `define "iyup.labels"` - Creates a reusable template in `_helpers.tpl`
- `include "iyup.labels" .` - Calls that template and passes the current context (`.`)
- `nindent X` - Adds a newline and indents the rendered block by `X` spaces so YAML stays valid

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started commands
- [Deployment Guide](DEPLOYMENT.md) - Helm and Kubernetes commands
- [Architecture](ARCHITECTURE.md) - Component details
- [API Reference](API.md) - API endpoints
