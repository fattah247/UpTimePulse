# Deployment

## Docker Compose

Run:

```bash
cp .env.example .env
docker compose up -d
docker compose ps
```

Stop:

```bash
docker compose down
```

Host ports come from `.env` when they are overridden there.

## Helm render check

Run:

```bash
helm lint ./charts/iyup
helm template iyup ./charts/iyup
```

That is the Kubernetes claim this repo makes today: the chart renders cleanly.

## Optional local cluster path

For a local Minikube run:

```bash
minikube start
eval "$(minikube -p minikube docker-env)"
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
helm upgrade --install iyup ./charts/iyup
```

The chart uses service port `80` for `api-gateway` and target port `8080`.
