# Demo Commands

```bash
set -a
test -f .env && . ./.env
set +a

API_GATEWAY_PORT="${API_GATEWAY_PORT:-8080}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-9093}"
```

```bash
docker compose up -d
docker compose ps
```

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/healthz"
```

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/status" | python3 -m json.tool
```

```bash
curl -fsS "http://localhost:${API_GATEWAY_PORT}/metrics" | head -40
```

```bash
curl -fsS "http://localhost:${PROMETHEUS_PORT}/-/ready"
```

```bash
curl -fsS "http://localhost:${PROMETHEUS_PORT}/api/v1/targets" | python3 -m json.tool
```

```bash
helm template iyup ./charts/iyup
```

```bash
./scripts/verify-local.sh
```
