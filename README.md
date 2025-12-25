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
