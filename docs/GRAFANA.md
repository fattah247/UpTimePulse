# Grafana

## Local provisioning

Docker Compose mounts:

- `config/grafana-datasources.yml`
- `config/grafana-dashboards.yml`
- `monitoring/grafana-dashboard.json`

That is what provisions the local dashboard automatically.

## Local check

Open:

```text
http://localhost:3000
```

Default login in Docker Compose:

- username: `admin`
- password: `admin` unless `GRAFANA_PASSWORD` overrides it

The dashboard name is `iYup Dashboard`.

## If a panel looks wrong

Check Prometheus first:

```bash
curl -fsS http://localhost:9090/api/v1/targets | python3 -m json.tool
```

Then inspect the raw queries behind the panels:

```bash
python3 scripts/inspect_prometheus_data.py
```

Or run the broader validation pass:

```bash
python3 scripts/validate_prometheus_data.py
```

## Helm note

The chart renders Grafana resources, but this repo only proves Docker Compose dashboard provisioning with screenshots.
