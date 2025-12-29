# UptimePulse

![Kubernetes](https://img.shields.io/badge/Kubernetes-1.29-blue)
![Prometheus](https://img.shields.io/badge/Prometheus-2.48-orange)
![Grafana](https://img.shields.io/badge/Grafana-10.3-informational)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)

Lightweight uptime + latency stack for learning Kubernetes, Prometheus, and real‑world SRE workflows — no cloud lock‑in, no managed magic.

## Table of Contents

- [Architecture overview](#architecture-overview)
- [Architecture & template map (detailed)](ARCHITECTURE.md)
- [Project layout](#project-layout)
- [Quickstart (local Docker)](#quickstart-local-docker)
- [Quickstart (Minikube)](#quickstart-minikube)
- [API Gateway Quickstart](#api-gateway-fastapi-quickstart)
- [API Endpoints](#api-endpoints-what-they-actually-do)
- [Command Notes](#command-notes)
- [Flag Cheat Sheet](#flag-cheat-sheet)
- [Why These Pieces Exist](#why-these-pieces-exist)
- [Metrics Cheat Sheet](#metrics-cheat-sheet)
- [Grafana Dashboard](#grafana-dashboard-what-it-shows-and-how-to-wire-it-up)
- [Troubleshooting](#troubleshooting-notes)
- [Rebuild From Scratch](#rebuild-everything-from-scratch)
- [What I Learned](#what-i-learned-and-why-this-exists)

## Architecture overview
Here’s the quick mental model:

Helm renders the chart; `ping-agent` reads its target list from a ConfigMap (`/config/targets.json`), pings those URLs, and exposes `/metrics`. Prometheus scrapes it (and `api-gateway`), stores time‑series data, and Grafana draws the graphs. The `api-gateway` reads ping‑agent metrics and exposes JSON summaries so a client doesn’t have to read raw Prometheus text. Alerts go through Alertmanager and land in a tiny logger service for now.

Data path: `ping-agent` → `Prometheus` → `Grafana`  
API path: `client` → `api-gateway` → `ping-agent` metrics

Full diagrams and a template-to-resource map live in `ARCHITECTURE.md`.

```mermaid
flowchart TB
  linkStyle default stroke-width:2px
  classDef group fill:#f7f7f7,stroke:#cccccc,stroke-width:2px
  classDef config fill:#e0f2fe,stroke:#0284c7,stroke-width:2px
  classDef service fill:#dcfce7,stroke:#16a34a,stroke-width:2px
  classDef monitoring fill:#fef3c7,stroke:#d97706,stroke-width:2px
  classDef alerting fill:#fee2e2,stroke:#dc2626,stroke-width:2px

  subgraph Deploy["Deployment"]
    helm[Helm chart]
    k8s[Kubernetes resources]
    helm --> k8s
  end

  subgraph Config["Configuration"]
    targets[ConfigMap<br/>targets.json]
  end

  subgraph Services["Services"]
    ping[ping-agent<br/>Pings URLs]
    api[api-gateway<br/>REST API]
    metrics[ping-agent<br/>/metrics endpoint]
  end

  subgraph Monitoring["Monitoring"]
    prom[Prometheus<br/>Scrapes & stores]
    grafana[Grafana<br/>Dashboards]
  end

  subgraph Alerting["Alerting"]
    alert[Alertmanager<br/>Routes alerts]
    logger[alert-logger<br/>Logs alerts]
  end

  subgraph Client["Client"]
    client[Client]
  end

  targets -->|"provides targets"| ping
  ping -->|"exposes"| metrics
  client -->|"HTTP request"| api
  api -->|"reads metrics"| metrics
  prom -->|"scrapes"| metrics
  prom -->|"scrapes"| api
  prom -->|"queries data"| grafana
  prom -->|"sends alerts"| alert
  alert -->|"webhook"| logger

  class Deploy,Config,Services,Monitoring,Alerting,Client group
  class targets config
  class ping,api,metrics service
  class prom,grafana monitoring
  class alert,logger alerting
```

## Project layout
- `services/` contains the application services (ping-agent, api-gateway, dashboard-ui).
- `charts/uptimepulse/` is the Helm chart (templates + values).
- `ci-cd/` contains legacy CI/CD pipeline configuration (kept for reference).
- `.github/workflows/` is the active CI workflow location.
- `monitoring/` contains the Grafana dashboard JSON.
- `terraform/` contains infrastructure as code to provision cloud resources.
- `docs/` removed (the root `README.md` is the single source of truth).

## Quickstart (local Docker)
Run ping‑agent locally:

```
cd services/ping-agent
docker build -t ping-agent:dev .
docker run --rm ping-agent:dev
```

## Quickstart (Minikube)
Ping‑agent in Minikube:

```
minikube start
kubectl config use-context minikube
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
helm install uptimepulse ./charts/uptimepulse
kubectl port-forward svc/uptimepulse-ping-agent 18080:8080
```

In another terminal:

```
curl -v http://localhost:18080/metrics
```

To remove the stack:
```
helm uninstall uptimepulse
```

For the command explanations, jump to [Command Notes](#command-notes) and [Flag Cheat Sheet](#flag-cheat-sheet).

## API Gateway (FastAPI) Quickstart
Build and run the API gateway in Minikube:

```
eval $(minikube -p minikube docker-env)
docker build -t api-gateway:latest services/api-gateway
helm upgrade --install uptimepulse ./charts/uptimepulse
kubectl port-forward svc/uptimepulse-api-gateway 8080:8080
```

Test it:

```
curl -v http://localhost:8080/healthz
```

Note: `api-gateway` uses `imagePullPolicy: IfNotPresent`. Build inside Minikube or it won’t find the image. (Ask me how I know.)

What each command means:
- `eval $(minikube -p minikube docker-env)` points Docker at Minikube's Docker daemon.
- `docker build -t api-gateway:latest services/api-gateway` builds the image inside Minikube.
- `helm upgrade --install uptimepulse ./charts/uptimepulse` applies the Helm chart (create or update).
- `kubectl port-forward svc/uptimepulse-api-gateway 8080:8080` tunnels local port `8080` to the Service.

## API Endpoints (What They Actually Do)
Endpoints from `api-gateway`:

- `GET /healthz` → simple healthcheck.
- `GET /targets` → list monitored URLs (from `PING_TARGET_URLS`).
- `GET /uptime-summary` → success/failure counts + availability %.
- `GET /metrics` → Prometheus metrics for api‑gateway itself.

## Command Notes
Short explanations of the commands used above.

### Minikube and kubectl
- `minikube start` starts a local Kubernetes cluster.
- `kubectl config use-context minikube` points `kubectl` at that cluster.
- `eval $(minikube -p minikube docker-env)` points Docker at Minikube's Docker daemon.
- `helm install uptimepulse ./charts/uptimepulse` installs the chart into the cluster.
- `helm upgrade --install uptimepulse ./charts/uptimepulse` re‑applies chart changes.
- `kubectl port-forward svc/uptimepulse-ping-agent 18080:8080` tunnels a Service port to your machine.

### Docker
- `docker build -t ping-agent:dev .` builds and tags an image from the current directory.
- `docker run --rm ping-agent:dev` runs the image and deletes the container after exit.
- `docker ps` lists running containers.
- `docker ps -a` lists all containers, including stopped.
- `docker images` lists local images.
- `docker stop <container>` stops a running container.

### Curl
- `curl -v http://localhost:18080/metrics` sends an HTTP request and shows verbose output.

## Flag Cheat Sheet
Common flags used in this project:

- `-f` = read from file (used by `kubectl`)
- `-v` = verbose output (used by `curl`)
- `-t` = tag name (used by `docker build`)
- `-p` = profile name (used by `minikube`)
- `--rm` = remove container after exit (used by `docker run`)

## Why these pieces exist
For term definitions (ConfigMap, PVC, HPA, Ingress, etc.), see `ARCHITECTURE.md#dictionary-terms-used-in-this-doc`.

### Ingress (what it means)
Ingress is the Kubernetes “front door” for HTTP. It maps a hostname/path to a Service (like `api-gateway`) so you can reach it without port‑forwarding. It only works if an Ingress controller (e.g., NGINX) is installed. In this chart, it’s off by default (`ingress.enabled: false`).

### HPA (what it means)
HPA = Horizontal Pod Autoscaler. It automatically scales the number of pod replicas based on metrics (usually CPU). In this chart, the HPA targets `api-gateway` and scales between 1–3 replicas when CPU goes high.

### Metrics producer (ping-agent)
This is the heart of the system. If this isn’t running, everything else is just watching silence. It pings a URL, then exposes:
- counters (`ping_success_total`, `ping_failure_total`)
- histogram (`ping_latency_seconds`)
- `/metrics` for scraping
- targets come from `/config/targets.json` (mounted ConfigMap); env fallback exists only if the file is missing

Without this, there’s nothing to observe.

### Metrics collection (Prometheus)
Prometheus pulls `/metrics` every 15s and stores the history. That’s the difference between “I can see a number now” and “I can graph the last 24 hours.”

Retention/storage notes:
- Retention is set to `14d` via `--storage.tsdb.retention.time=14d` in `charts/uptimepulse/templates/prometheus-deployment.yaml`.
- PVC (see Dictionary) size is `5Gi` in `charts/uptimepulse/templates/prometheus-pvc.yaml`.
- Prometheus storage docs: [https://prometheus.io/docs/prometheus/latest/storage/](https://prometheus.io/docs/prometheus/latest/storage/)

Sizing approach (practical):
- After 24h of scraping, check `prometheus_tsdb_head_series` and `prometheus_tsdb_head_chunks`.
- Look at disk usage from inside the pod: `du -sh /prometheus`.
- Extrapolate: if 24h uses 1Gi, then 7d is roughly 7Gi (plus headroom).

PromQL to sanity‑check volume:
```
prometheus_tsdb_head_series
prometheus_tsdb_head_chunks
rate(prometheus_tsdb_head_samples_appended_total[5m])
```

Automated snapshot (script):
- `scripts/prometheus-sizing.sh` collects the head metrics and `/prometheus` disk usage.
- Run: `scripts/prometheus-sizing.sh` (uses port 9090 by default).

### Metrics cheat sheet
- `ping_success_total` (counter) → Stat panel
- `ping_failure_total` (counter) → Stat panel
- `ping_latency_seconds` (histogram) → Heatmap/Histogram panel
- `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])` (avg latency) → Line graph

## Why Go Needs `go.mod` and `go.sum`
These are standard Go module files.

- `go.mod` declares the module name, the Go version, and direct dependencies.
- `go.sum` records exact checksums so builds are reproducible.

If `go.sum` is missing, Docker builds will break — guaranteed.

## What you’ve learned so far
Concrete skills you now have:

- Build a Go service that emits Prometheus metrics.
- Package it with Docker and run it locally.
- Run a Minikube cluster and deploy with Kubernetes YAML.
- Connect Prometheus → Grafana and see live graphs.
- Debug real issues (image not in Minikube, stale pod during rollout, port‑forward failures).

## How everything connects
Short version:

`ping-agent` → `Prometheus` → `Grafana`

The Service gives `ping-agent` a stable DNS name, Prometheus scrapes it, and Grafana reads Prometheus. The `api-gateway` sits alongside to expose a human‑friendly JSON API.

## What Each YAML File Is Doing (and Why)
If a term is unclear (ConfigMap, PVC, Secret, etc.), jump to `ARCHITECTURE.md#dictionary-terms-used-in-this-doc`.
### `charts/uptimepulse/templates/ping-agent-deployment.yaml`
Runs the ping-agent container.

- `apiVersion`, `kind`: identifies a Deployment.
- `metadata.name`: the deployment name.
- `spec.replicas`: number of pods.
- `spec.selector` + `template.metadata.labels`: ties the Deployment to its Pods.
- `containers.image`: which image to run (`ping-agent:latest`).
- `imagePullPolicy: IfNotPresent`: use local image in Minikube if available.
- `ports.containerPort`: declares the app port (8080).
- `volumeMounts`: mounts `/config/targets.json` from the ConfigMap.

### `charts/uptimepulse/templates/ping-targets-configmap.yaml`
Stores the target list as JSON so ping-agent can read it from `/config/targets.json`.

### `charts/uptimepulse/templates/ping-agent-service.yaml`
Exposes ping-agent inside the cluster so Prometheus can scrape it.

- `kind: Service`: stable DNS and load-balanced access.
- `selector`: matches pods labeled `app: ping-agent`.
- `port`/`targetPort`: forwards 8080 to the pod.

### `charts/uptimepulse/templates/api-gateway-deployment.yaml`
Runs the FastAPI gateway.

- `containerPort: 8080` matches the `uvicorn` port.
- `env.PING_AGENT_METRICS_URL` points at `http://ping-agent:8080/metrics`.
- `env.PING_TARGET_URLS` mirrors the target list used by ping-agent.
- `livenessProbe`/`readinessProbe` hit `/healthz`.
- Prometheus scrape annotations enable `/metrics` scraping.

### `charts/uptimepulse/templates/api-gateway-service.yaml`
Service fronting the API gateway.

- Used for port‑forward and Prometheus scraping (`api-gateway:8080`).

### `charts/uptimepulse/templates/prometheus-configmap.yaml`
Holds Prometheus configuration (ConfigMap; see Dictionary).

- `kind: ConfigMap`: stores `prometheus.yml` as data.
- `scrape_interval`: how often Prometheus scrapes.
- `scrape_configs`: targets to scrape (`ping-agent` and `api-gateway`).

### `charts/uptimepulse/templates/prometheus-deployment.yaml`
Runs Prometheus and mounts the config (Deployment; see Dictionary).

- `containers.image`: Prometheus image version.
- `args`: tells Prometheus where the config and data directory are.
- `volumeMounts` + `volumes`: mounts the ConfigMap to `/etc/prometheus`.
- `volumeMounts` + `volumes`: mounts a PVC at `/prometheus` for data persistence.
- `ports.containerPort: 9090`: Prometheus UI and API.
- `strategy.type: Recreate`: avoids PVC lock conflicts by ensuring a single pod.

### `charts/uptimepulse/templates/prometheus-service.yaml`
Exposes Prometheus inside the cluster.

- `selector`: matches the Prometheus pod.
- `port`/`targetPort`: exposes `9090` for UI/API access.

### `charts/uptimepulse/templates/prometheus-pvc.yaml`
Persists Prometheus time-series data across restarts (PVC; see Dictionary).

- `kind: PersistentVolumeClaim`: requests storage from the cluster.
- `storage: 5Gi`: size of the requested volume.

### `charts/uptimepulse/templates/alert-rules-configmap.yaml`
Prometheus alert rules (ConfigMap; see Dictionary).

- `alert: TargetDown` fires when `ping_failure_total` spikes.
- `expr: increase(ping_failure_total[1m]) > 2`
- `for: 1m` keeps it from flapping on a single miss.

### `charts/uptimepulse/templates/alertmanager-configmap.yaml`
Alertmanager routing config (ConfigMap; see Dictionary).

- Routes all alerts to a webhook receiver called `stdout`.
- That receiver points to `alert-logger` for now.
- SMTP settings are read from `alertmanager-smtp` via env vars.

### `charts/uptimepulse/templates/alertmanager-deployment.yaml`
Runs Alertmanager (Deployment; see Dictionary).

- Exposes port `9093`.
- Uses the config from `alertmanager-config`.
- Loads SMTP credentials from the Secret.

### `charts/uptimepulse/templates/alertmanager-service.yaml`
Cluster service for Alertmanager (Service; see Dictionary).

- Used by Prometheus `alertmanagers` config.

### `charts/uptimepulse/templates/alert-logger-deployment.yaml`
Tiny HTTP echo service to print alert payloads to stdout (Deployment; see Dictionary).

- Placeholder for Slack/email later.

### `charts/uptimepulse/templates/alert-logger-service.yaml`
Cluster service for `alert-logger` (Service; see Dictionary).

### `charts/uptimepulse/templates/alertmanager-secret.yaml`
SMTP credentials for Alertmanager email (Secret; see Dictionary).

- Override these with `--set alert.smtp.*` or a private values file (see `charts/uptimepulse/values.local.yaml`).

### `.github/workflows/ci.yml`
Single CI pipeline for Go + Python + Docker builds.

- Go: `gofmt`, `go vet`, `go test`.
- Python: `py_compile`, `unittest`.
- Docker: builds images for `ping-agent` and `api-gateway`.

### `.gitignore`
Keeps secrets and local files out of git.

- If you create a local values override for SMTP credentials, don’t commit it.

### `charts/uptimepulse/templates/grafana-deployment.yaml`
Runs Grafana (Deployment; see Dictionary).

- `containers.image`: Grafana image version.
- `ports.containerPort: 3000`: Grafana UI port.
- `volumeMounts` + `volumes`: mounts a PVC at `/var/lib/grafana` so dashboards/users persist.

### `charts/uptimepulse/templates/grafana-service.yaml`
Exposes Grafana in the cluster (Service; see Dictionary).

- `type: ClusterIP`: internal-only service by default.
- `port`/`targetPort`: exposes `3000`.

### `charts/uptimepulse/templates/grafana-pvc.yaml`
Persists Grafana dashboards and user settings across restarts (PVC; see Dictionary).

- `kind: PersistentVolumeClaim`: requests storage from the cluster.
- `storage: 5Gi`: size of the requested volume.

## Grafana Dashboard: What It Shows, and How to Wire It Up
Grafana dashboards are JSON documents. We keep one at `monitoring/grafana-dashboard.json`.

Key fields inside the JSON:
- `title`
- `refresh`
- `panels`
- `targets` (PromQL)
- `gridPos`

Panels in this dashboard:
- Total API Requests (5m) → `sum(increase(api_gateway_requests_total[5m]))`
- Successful Pings → `ping_success_total`
- Failed Pings → `ping_failure_total`
- Availability % → `100 * (ping_success_total / (ping_success_total + ping_failure_total))`
- Requests by Status (rate) → `sum by (status) (rate(api_gateway_requests_total[1m]))`
- Ping Success/Failures (rate) → `rate(ping_success_total[1m])`, `rate(ping_failure_total[1m])`
- Requests by Path (5m) → `sum by (path) (increase(api_gateway_requests_total[5m]))`
- API Latency Histogram (bucket rate) → `sum(rate(api_gateway_request_duration_seconds_bucket[5m])) by (le)`
- Ping Latency Histogram (1m rate) → `rate(ping_latency_seconds_bucket[1m])`
- Average Ping Latency (s) → `rate(ping_latency_seconds_sum[1m]) / rate(ping_latency_seconds_count[1m])`

Dashboard coverage summary:
| Feature                               | PromQL      | Panel Type   | Purpose                             |
| ------------------------------------- | ----------- | ------------ | ----------------------------------- |
| Uptime %                              | ✅          | Stat         | System-wide reliability             |
| API Gateway total requests            | ✅          | Stat         | Traffic level                       |
| API Gateway status breakdown          | ✅          | Time Series  | Error monitoring                    |
| API Gateway latency histogram         | ✅          | Heatmap      | Performance under load              |
| Table of targets with success/failure | ➖ (via API) | Table/Stat   | Drilldown per target (stretch goal) |
| Alerts (e.g., ping failures)          | ✅          | Alert config | Early warning system                |

Apply the dashboard:
1) Port-forward Grafana:
```
kubectl port-forward svc/uptimepulse-grafana 3000:3000
```
2) Open Grafana and login:
- URL: `http://localhost:3000`
- Default credentials: `admin` / `admin` (Grafana will prompt to change)
3) Add Prometheus as a data source:
- Connections → Data sources → Add data source → Prometheus
- URL: `http://uptimepulse-prometheus:9090`
- Save & Test
4) Import the dashboard JSON:
- Dashboards → New → Import
- Upload `monitoring/grafana-dashboard.json`
- Select the Prometheus data source
- Import

## Screenshots (placeholders)
Add screenshots here later:
- Architecture diagram (simple box/arrow flow).
- Grafana dashboard with uptime + API panels visible.
- Prometheus Targets page (`/targets`) showing ping-agent and api-gateway as UP.
- API Gateway `/uptime-summary` response in terminal (curl output).

## Persistence notes
Prometheus and Grafana are configured with PVCs so data and dashboards survive restarts.  
If you redeploy the Pods, your metrics history and Grafana settings should remain.

## Troubleshooting notes
### Goal
Run the ping-agent in Docker and in Minikube, expose Prometheus metrics on `:8080/metrics`, and verify it with `curl`.

### Problems observed
- Docker couldn't connect to the daemon (Docker Desktop not running or shell pointed at Minikube's daemon).
- `ErrImageNeverPull` in Kubernetes (image not available inside Minikube).
- Helm install failed from the wrong working directory (chart path not found).
- Helm failed with template parse errors (escaped quotes inside templates).
- Port-forward to `:8080` returned `connection refused` (pod was running an old image without the metrics server).
- Port-forward to the API gateway failed because the Service exposed port 80, not 8080.
- `/uptime-summary` returned `0%` availability even though `/metrics` showed success counts.
- Go build errors (missing `go.sum`, Go version mismatch, syntax errors in `main.go`).
- Prometheus/Grafana rollouts stuck due to PVC lock during rolling updates.
- Alerts not visible: check `alert-logger` pod logs.

### Resolutions
- Start Docker Desktop; reset Docker env with `eval $(minikube docker-env -u)` when needed.
- Build the image inside Minikube (`eval $(minikube -p minikube docker-env)` + `docker build ...`).
- Use repo root for `helm install uptimepulse ./charts/uptimepulse`.
- Fix template quoting by using single-quoted strings (avoid `\"` in Helm templates).
- Start Minikube and select the right context (`minikube start`, `kubectl config use-context minikube`).
- The metrics parser in `services/api-gateway/main.py` was too strict (expected unlabeled counters). Fix by reading label values like `target="..."` and summing `ping_success_total{target="..."}` and `ping_failure_total{target="..."}` per target.
- Update Dockerfile to include `go.sum` and use the correct Go version.
- Fix `main.go` typos and ensure `http.ListenAndServe(":8080", nil)` is running.
- Use `strategy: Recreate` for Prometheus/Grafana when using PVCs, then delete old pods so only one holds the lock.
- Grafana panels may go blank briefly during Prometheus rollouts. Give it ~30s.
- Keep `monitoring/grafana-dashboard.json` for Grafana import and install Kubernetes resources via Helm.
- For alerts, check `kubectl logs deploy/uptimepulse-alert-logger` to see raw payloads.
- If Grafana rollouts keep hanging, set `strategy: Recreate` in `charts/uptimepulse/templates/grafana-deployment.yaml`.
- If you port-forward the API gateway, use `kubectl port-forward svc/uptimepulse-api-gateway 8080:80` (or set `service.apiGatewayPort: 8080`).

### Verification steps
- `kubectl logs -l app.kubernetes.io/component=ping-agent --tail=20` shows ping logs and metrics server start line.
- `kubectl port-forward svc/uptimepulse-ping-agent 18080:8080`
- `curl -v http://localhost:18080/metrics` returns `HTTP/1.1 200 OK` and metric output.

## Rebuild Everything From Scratch
This is a complete, copy‑paste path to rebuild and validate everything.

### 1) Build images inside Minikube
```
cd /Users/muhammadfattah/Documents/Projects/Git/Active/UpTimePulse
eval $(minikube -p minikube docker-env)
docker build -t ping-agent:latest services/ping-agent
docker build -t api-gateway:latest services/api-gateway
```

### 2) Install or upgrade the Helm chart
```
helm upgrade --install uptimepulse ./charts/uptimepulse
```

If you need SMTP credentials, set them via a values override:
```
helm upgrade --install uptimepulse ./charts/uptimepulse \\
  --set alert.smtp.user="you@gmail.com" \\
  --set alert.smtp.password="APP_PASSWORD" \\
  --set alert.smtp.from="you@gmail.com" \\
  --set alert.smtp.to="alerts@example.com"
```

Local override file (to make secrets stay out of git):
```
helm upgrade --install uptimepulse ./charts/uptimepulse -f charts/uptimepulse/values.local.yaml
```
Note: `charts/uptimepulse/values.local.yaml` is git‑ignored on purpose.

Feature toggles (values.yaml):
```
ingress:
  enabled: true
  host: uptimepulse.local

hpa:
  enabled: true
```

Helm sanity checks:
```
helm lint charts/uptimepulse
helm template uptimepulse ./charts/uptimepulse | kubectl apply --dry-run=client -f -
```

### 3) Restart deployments and wait for readiness
```
kubectl rollout restart deployment uptimepulse-ping-agent
kubectl rollout restart deployment uptimepulse-api-gateway
kubectl rollout restart deployment uptimepulse-prometheus
kubectl rollout restart deployment uptimepulse-grafana

kubectl rollout status deployment uptimepulse-ping-agent
kubectl rollout status deployment uptimepulse-api-gateway
kubectl rollout status deployment uptimepulse-prometheus
kubectl rollout status deployment uptimepulse-grafana
```

### 4) Port-forward and test endpoints
```
kubectl port-forward svc/uptimepulse-ping-agent 18080:8080
kubectl port-forward svc/uptimepulse-api-gateway 8080:8080
kubectl port-forward svc/uptimepulse-prometheus 9090:9090
kubectl port-forward svc/uptimepulse-grafana 3000:3000
```

In separate terminals:
```
curl -v http://localhost:18080/metrics
curl -v http://localhost:8080/healthz
curl -v http://localhost:8080/uptime-summary
```

### 5) Grafana
- Open `http://localhost:3000`
- Add Prometheus data source: `http://uptimepulse-prometheus:9090`
- Import `monitoring/grafana-dashboard.json`

## Quick sanity checks
- Prometheus targets are UP: `http://localhost:9090/targets`
- Alert rule exists: `http://localhost:9090/rules` (look for `TargetDown`)
- Alertmanager is reachable: `http://localhost:9093/#/alerts`
- Alert output shows in logger: `kubectl logs deploy/uptimepulse-alert-logger --tail=50`
- API works:
  - `curl -v http://localhost:8080/healthz`
  - `curl -v http://localhost:8080/uptime-summary`
- Ping metrics are exposed: `curl -v http://localhost:18080/metrics`
- PVCs are bound: `kubectl get pvc`

### Trigger an alert (quick test)
1) Set a bad target in `charts/uptimepulse/values.yaml` (e.g., `https://example.invalid`).
2) Apply and wait:
```
helm upgrade --install uptimepulse ./charts/uptimepulse
```
3) Wait 1–2 minutes, then check:
- `http://localhost:9090/alerts`
- `kubectl logs deploy/alert-logger --tail=50`

## What I Learned (and Why This Exists)
I built this as a fast, messy crash course in the stuff you only learn once it breaks: container builds inside Minikube, Prometheus scraping, Grafana dashboards, and *why rollouts + PVCs can be a pain*. It’s a real‑ish SRE toy stack, not a polished product. I’m keeping it around because it makes failure modes visible and repeatable.
