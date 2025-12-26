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

Run the ping-agent in Minikube and check metrics (with explanations):

```
minikube start
kubectl config use-context minikube
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
kubectl apply -f k8s/ping-agent-deployment.yaml
kubectl rollout restart deployment ping-agent
kubectl port-forward deploy/ping-agent 18080:8080
```

What each part means:
- `minikube start` starts a local Kubernetes cluster.
- `kubectl config use-context minikube` points `kubectl` at that cluster.
- `eval $(minikube -p minikube docker-env)`
  - `minikube docker-env` prints shell exports so Docker talks to Minikube's Docker daemon.
  - `$(...)` runs a command and substitutes its output.
  - `eval` executes that output in your current shell so the env vars take effect.
  - `-p minikube` selects the Minikube profile named `minikube`.
- `docker build -t ping-agent:latest services/ping-agent`
  - `build` creates an image from a Dockerfile.
  - `-t` tags the image with a name and tag (`ping-agent:latest`).
  - `services/ping-agent` is the build context.
- `kubectl apply -f k8s/ping-agent-deployment.yaml`
  - `apply` creates/updates resources.
  - `-f` means "read from file".
- `kubectl rollout restart deployment ping-agent` restarts the pods so they use the new image.
- `kubectl port-forward deploy/ping-agent 18080:8080`
  - Port-forwarding opens a local port (`18080`) and tunnels it to the pod's port (`8080`).
  - This lets you access the pod without creating a Service or Ingress.

In another terminal:

```
curl -v http://localhost:18080/metrics
```

- `curl` is a command-line HTTP client for making requests.
- `-v` prints verbose connection and response details (useful for debugging).

## Command Notes
Short explanations of common commands used in this repo.

- `kubectl apply -f k8s/ping-agent-deployment.yaml`
  - `apply` creates/updates resources.
  - `-f` means "read from file".
- `eval $(minikube -p minikube docker-env)`
  - `minikube docker-env` prints shell exports to point Docker at Minikube's Docker daemon.
  - `$(...)` runs a command and substitutes its output.
  - `eval` executes that output in the current shell so the env vars take effect.
  - `-p minikube` selects the Minikube profile named `minikube`.

### Docker Commands
- `docker build -t ping-agent:dev .`
  - `build` creates an image from a Dockerfile.
  - `-t ping-agent:dev` tags the image with a name and tag.
  - `.` is the build context (current directory).
- `docker run --rm ping-agent:dev`
  - `run` starts a container from the image.
  - `--rm` deletes the container when it exits.
  - `ping-agent:dev` is the image name:tag to run.

Extra commands you may see:
- `docker ps` lists running containers.
- `docker ps -a` lists all containers, including stopped.
- `docker images` lists local images.
- `docker stop <container>` stops a running container.

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

## Go Files (go.mod and go.sum)
These are the standard files used by Go modules.

- `go.mod` declares the module name, the Go version, and the direct dependencies your code uses.
- `go.sum` records exact checksums of all module versions (direct and indirect) so builds are reproducible and verified.

Why they matter:
- Without `go.mod`, the Go toolchain doesn't know which dependencies to use.
- Without `go.sum`, the build can't verify module integrity (and Docker builds will fail).

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
