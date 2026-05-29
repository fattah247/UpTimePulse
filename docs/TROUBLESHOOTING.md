# Troubleshooting

## Docker daemon is not available

Run:

```bash
docker ps
```

If that fails, start Docker Desktop or switch back from the Minikube Docker context:

```bash
eval "$(minikube docker-env -u)"
```

## `api-gateway` is up but the host port is different

Check `.env` first:

```bash
cat .env
docker compose ps
```

This repo supports host port overrides such as `API_GATEWAY_PORT=8081`.

## Prometheus targets are down

Run:

```bash
curl -fsS http://localhost:9090/api/v1/targets | python3 -m json.tool
docker compose ps
```

If `ping-agent` or `api-gateway` is unhealthy, restart the stack:

```bash
docker compose up -d
```

## Grafana panel has no data

Check Prometheus before Grafana:

```bash
curl -fsS http://localhost:9090/api/v1/targets | python3 -m json.tool
python3 scripts/inspect_prometheus_data.py
```

## Minikube cannot pull the images

Build inside the Minikube Docker context:

```bash
eval "$(minikube -p minikube docker-env)"
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
```

## Helm render fails

Run:

```bash
helm lint ./charts/iyup
helm template iyup ./charts/iyup
```

Most failures here come from chart values or template syntax, not from a live cluster.
