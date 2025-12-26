# UptimePulse

Placeholder project skeleton for a simple uptime monitoring platform.

## Structure
- `services/` contains the application services.
- `k8s/` contains Kubernetes manifests.
- `ci-cd/` contains CI/CD pipeline configuration.
- `monitoring/` contains Prometheus and Grafana configuration.
- `terraform/` contains infrastructure as code (optional).
- `docs/` contains documentation and diagrams.

## Notes
This repository currently contains placeholder files only.

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

## Docker Command Notes
Common Docker workflow used for the ping-agent service.

```
cd services/ping-agent
docker build -t ping-agent:dev .
docker run --rm ping-agent:dev
```

- `cd services/ping-agent` changes into the service directory.
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

## Troubleshooting Notes (What Happened and How We Fixed It)
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
