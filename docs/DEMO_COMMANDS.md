# Demo Commands

Load local ports:

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"
```

## Start stack

```bash
docker compose up -d
docker compose ps
```

## API health

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"
```

## API status

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" | python3 -m json.tool
```

## API metrics

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics" | head -40
```

## Prometheus readiness

```bash
curl -fsS "http://localhost:${PROMETHEUS_PORT}/-/ready"
```

## Prometheus targets API

```bash
curl -fsS "http://localhost:${PROMETHEUS_PORT}/api/v1/targets" | python3 -m json.tool
```

## Helm rendering

```bash
helm template iyup ./charts/iyup
```

## Local verification

```bash
./scripts/verify-local.sh
```
