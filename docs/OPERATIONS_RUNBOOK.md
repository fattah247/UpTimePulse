# Operations Runbook

Load local ports first:

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PING_AGENT_PORT="${PING_AGENT_PORT:-18080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"
```

## Start

```bash
docker compose up -d
```

## Stop

```bash
docker compose down
```

## Check containers

```bash
docker compose ps
```

## Check API

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"
curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" | python3 -m json.tool
curl -fsS "http://localhost:${API_GATEWAY_PORT}/targets" | python3 -m json.tool
curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics"
```

## Check ping-agent metrics

```bash
curl -fsS "http://localhost:${PING_AGENT_PORT}/metrics"
```

## Check Prometheus

```bash
curl -fsS "http://localhost:${PROMETHEUS_PORT}/-/ready"
curl -fsS "http://localhost:${PROMETHEUS_PORT}/api/v1/targets" | python3 -m json.tool
```

## Open Grafana and Alertmanager

```text
http://localhost:${GRAFANA_PORT}
http://localhost:${ALERTMANAGER_PORT}
```

## Check Helm rendering

```bash
helm lint ./charts/iyup
helm template iyup ./charts/iyup
```

## Run the local verification script

```bash
./scripts/verify-local.sh
```
