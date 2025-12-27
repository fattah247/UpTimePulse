# UptimePulse

Starter project for a simple uptime monitoring platform.

## Project Layout
- `services/` contains the application services.
- `k8s/` contains Kubernetes manifests.
- `ci-cd/` contains CI/CD pipeline configuration.
- `monitoring/` contains Prometheus and Grafana configuration.
- `terraform/` contains infrastructure as code (optional).
- `docs/` contains documentation and diagrams.

## Quickstart
Run the ping-agent locally with Docker:

```
cd services/ping-agent
docker build -t ping-agent:dev .
docker run --rm ping-agent:dev
```

Run the ping-agent in Minikube and check metrics:

```
minikube start
kubectl config use-context minikube
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
kubectl apply -f k8s/ping-agent-deployment.yaml
kubectl rollout restart deployment ping-agent
kubectl port-forward deploy/ping-agent 18080:8080
```

In another terminal:

```
curl -v http://localhost:18080/metrics
```

For command explanations, see [Command Notes](#command-notes) and [Flag Cheat Sheet](#flag-cheat-sheet) below.

## Command Notes
Short explanations of the commands used above.

### Minikube and kubectl
- `minikube start` starts a local Kubernetes cluster.
- `kubectl config use-context minikube` points `kubectl` at that cluster.
- `eval $(minikube -p minikube docker-env)` points Docker at Minikube's Docker daemon.
- `kubectl apply -f k8s/ping-agent-deployment.yaml` creates or updates resources from a file.
- `kubectl rollout restart deployment ping-agent` restarts pods to pick up new images/config.
- `kubectl port-forward deploy/ping-agent 18080:8080` tunnels a pod port to your machine.

### Docker
- `docker build -t ping-agent:dev .` builds and tags an image from the current directory.
- `docker run --rm ping-agent:dev` runs the image and deletes the container after exit.
- `docker ps` lists running containers.
- `docker ps -a` lists all containers, including stopped.
- `docker images` lists local images.
- `docker stop <container>` stops a running container.

### Curl
- `curl -v http://localhost:18080/metrics` sends an HTTP request and shows verbose output.

## Flag Cheat Sheet
Common flags used in this project:

- `-f` = read from file (used by `kubectl`)
- `-v` = verbose output (used by `curl`)
- `-t` = tag name (used by `docker build`)
- `-p` = profile name (used by `minikube`)
- `--rm` = remove container after exit (used by `docker run`)

## Why We Added Each Piece
This section explains the purpose behind each addition, not just the steps.

### Metrics Producer (ping-agent)
Goal: generate meaningful metrics inside the app so you can observe behavior.

What we added and why:
- A periodic HTTP ping loop to produce real uptime/latency data.
- `ping_success_total`, `ping_failure_total`, `ping_latency_seconds` so you can count outcomes and measure latency.
- A `/metrics` HTTP endpoint so external systems can scrape the metrics.
- A local `curl` check to confirm the metrics are emitted correctly.

This is the data source. By itself, it only shows the current state inside the app.

### Metrics Collection (Prometheus)
Goal: collect, store, and query metrics over time.

What Prometheus does:
- Scrapes `/metrics` on a schedule (default 15s).
- Stores time-series data so you can query history with PromQL.

Why it matters:
- Without Prometheus, metrics disappear on restart.
- You can't graph trends, alert, or analyze failures without storage.

### Metrics Cheat Sheet
- `ping_success_total` (counter) → Stat panel
- `ping_failure_total` (counter) → Stat panel
- `ping_latency_seconds` (histogram) → Heatmap/Histogram panel
- `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])` (avg latency) → Line graph

## Go Files (go.mod and go.sum)
These are the standard files used by Go modules.

- `go.mod` declares the module name, the Go version, and the direct dependencies your code uses.
- `go.sum` records exact checksums of all module versions (direct and indirect) so builds are reproducible and verified.

Why they matter:
- Without `go.mod`, the Go toolchain doesn't know which dependencies to use.
- Without `go.sum`, the build can't verify module integrity (and Docker builds will fail).

## What You Have Learned So Far
Core skills you picked up while building and running this project:

- Building a Go service that emits Prometheus metrics and exposes them on `/metrics`.
- Containerizing the service with Docker and understanding image tags and build contexts.
- Running a local Kubernetes cluster with Minikube and switching contexts.
- Using Deployments and Services to run and expose pods in Kubernetes.
- Wiring Prometheus to scrape metrics and validating output with `curl`.
- Adding Grafana for visualization and importing dashboards.
- Debugging common issues (wrong working directory, image not in Minikube, port-forward failures).

## How Everything Connects
The components form a simple metrics pipeline:

- `ping-agent` generates metrics and serves them on `:8080/metrics`.
- `ping-agent` Service gives the pod a stable DNS name for scraping.
- Prometheus reads `prometheus.yml` from a ConfigMap and scrapes `ping-agent`.
- Grafana queries Prometheus and visualizes the data with the dashboard JSON.

In short: ping-agent → Prometheus → Grafana.

## YAML Files Explained
Below is a short guide for each YAML file and why it exists.

### `k8s/ping-agent-deployment.yaml`
Runs the ping-agent container.

- `apiVersion`, `kind`: identifies a Deployment.
- `metadata.name`: the deployment name.
- `spec.replicas`: number of pods.
- `spec.selector` + `template.metadata.labels`: ties the Deployment to its Pods.
- `containers.image`: which image to run (`ping-agent:latest`).
- `imagePullPolicy: IfNotPresent`: use local image in Minikube if available.
- `ports.containerPort`: declares the app port (8080).

### `k8s/ping-agent-service.yaml`
Exposes ping-agent inside the cluster so Prometheus can scrape it.

- `kind: Service`: stable DNS and load-balanced access.
- `selector`: matches pods labeled `app: ping-agent`.
- `port`/`targetPort`: forwards 8080 to the pod.

### `k8s/prometheus-configmap.yaml`
Holds Prometheus configuration.

- `kind: ConfigMap`: stores `prometheus.yml` as data.
- `scrape_interval`: how often Prometheus scrapes.
- `scrape_configs`: targets to scrape (`ping-agent` and `api-gateway`).

### `k8s/prometheus-deployment.yaml`
Runs Prometheus and mounts the config.

- `containers.image`: Prometheus image version.
- `args`: tells Prometheus where the config and data directory are.
- `volumeMounts` + `volumes`: mounts the ConfigMap to `/etc/prometheus`.
- `ports.containerPort: 9090`: Prometheus UI and API.

### `k8s/prometheus-service.yaml`
Exposes Prometheus inside the cluster.

- `selector`: matches the Prometheus pod.
- `port`/`targetPort`: exposes `9090` for UI/API access.

### `monitoring/grafana-deployment.yaml`
Runs Grafana.

- `containers.image`: Grafana image version.
- `ports.containerPort: 3000`: Grafana UI port.

### `monitoring/grafana-service.yaml`
Exposes Grafana in the cluster.

- `type: ClusterIP`: internal-only service by default.
- `port`/`targetPort`: exposes `3000`.

## Grafana Dashboard (How It Works and How To Apply)
Grafana dashboards are JSON documents. We keep one at `monitoring/grafana-dashboard.json`.

### What’s Inside the Dashboard JSON
Key fields you’ll see:

- `title`: dashboard name shown in Grafana.
- `refresh`: auto-refresh interval.
- `panels`: list of visualizations.
- `targets`: PromQL queries for each panel.
- `gridPos`: panel position and size in the layout.

### Panels in This Dashboard
- Panel 1: `ping_success_total` (stat)
- Panel 2: `ping_failure_total` (stat)
- Panel 3: `rate(ping_latency_seconds_bucket[1m])` (heatmap)
- Panel 4: average latency line graph using  
  `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])`

### Apply the Dashboard in Grafana
1) Port-forward Grafana:

```
kubectl port-forward deployment/grafana 3000:3000
```

2) Open Grafana and login:
- URL: `http://localhost:3000`
- Default credentials: `admin` / `admin` (Grafana will prompt to change)

3) Add Prometheus as a data source:
- Connections → Data sources → Add data source → Prometheus
- URL: `http://prometheus:9090`
- Save & Test

4) Import the dashboard JSON:
- Dashboards → New → Import
- Upload `monitoring/grafana-dashboard.json`
- Select the Prometheus data source
- Import

## Troubleshooting Notes
This section captures the main issues we hit while running the ping-agent and how we resolved them.

### Goal
Run the ping-agent in Docker and in Minikube, expose Prometheus metrics on `:8080/metrics`, and verify it with `curl`.

### Problems Observed
- Docker couldn't connect to the daemon (Docker Desktop not running or shell pointed at Minikube's daemon).
- `ErrImageNeverPull` in Kubernetes (image not available inside Minikube).
- `kubectl apply` failed from the wrong working directory (`k8s/` path not found).
- `kubectl apply` failed with OpenAPI errors (cluster not running or context stale).
- Port-forward to `:8080` returned `connection refused` (pod was running an old image without the metrics server).
- Go build errors (missing `go.sum`, Go version mismatch, syntax errors in `main.go`).

### Resolutions
- Start Docker Desktop; reset Docker env with `eval $(minikube docker-env -u)` when needed.
- Build the image inside Minikube (`eval $(minikube -p minikube docker-env)` + `docker build ...`).
- Use repo root for `kubectl apply -f k8s/...`.
- Start Minikube and select the right context (`minikube start`, `kubectl config use-context minikube`).
- Rebuild and restart the deployment to pick up the new binary (`kubectl rollout restart deployment ping-agent`).
- Update Dockerfile to include `go.sum` and use the correct Go version.
- Fix `main.go` typos and ensure `http.ListenAndServe(":8080", nil)` is running.

### Verification Steps
- `kubectl logs -l app=ping-agent --tail=20` shows ping logs and metrics server start line.
- `kubectl port-forward deploy/ping-agent 18080:8080`
- `curl -v http://localhost:18080/metrics` returns `HTTP/1.1 200 OK` and metric output.
