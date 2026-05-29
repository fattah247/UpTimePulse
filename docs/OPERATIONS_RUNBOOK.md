# Operations Runbook

Examples below assume the default ports from `.env.example`. If your `.env` overrides host ports, substitute those values.

## Start the stack

```bash
cp .env.example .env
docker compose up -d
```

## Stop the stack

```bash
docker compose down
```

## Check containers

```bash
docker compose ps
```

## Check API health

```bash
curl -fsS http://localhost:8080/healthz
```

## Check status API

```bash
curl -fsS http://localhost:8080/status | jq .
```

## Check targets

```bash
curl -fsS http://localhost:8080/targets | jq .
```

## Check metrics endpoint

```bash
curl -fsS http://localhost:8080/metrics
curl -fsS http://localhost:18080/metrics
```

## Check Prometheus readiness

```bash
curl -fsS http://localhost:9090/-/ready
```

## Check Prometheus targets

```bash
curl -fsS http://localhost:9090/api/v1/targets | jq .
```

## Open Grafana

```text
http://localhost:3000
```

Default credentials:

- username: `admin`
- password: `admin` unless overridden by `GRAFANA_PASSWORD`

## Open Alertmanager

```text
http://localhost:9093
```

## Run Helm validation

```bash
helm lint ./charts/iyup
helm template iyup ./charts/iyup
```

## Run local verification

```bash
./scripts/verify-local.sh
```
