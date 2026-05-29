# Quickstart

## Local Docker Compose path

Run:

```bash
cp .env.example .env
docker compose up -d
./scripts/verify-local.sh
```

Open:

- `http://localhost:8080/status`
- `http://localhost:9090/targets`
- `http://localhost:3000`
- `http://localhost:9093`

If `.env` overrides the host ports, use those values instead.

## Helm render path

Run:

```bash
helm lint ./charts/iyup
helm template iyup ./charts/iyup
```

## Optional Minikube path

Run:

```bash
minikube start
eval "$(minikube -p minikube docker-env)"
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
helm upgrade --install iyup ./charts/iyup
```
