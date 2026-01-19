import os
import re
import threading
import time

import requests
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
app = FastAPI()


PING_AGENT_METRICS_URL = os.getenv(
    "PING_AGENT_METRICS_URL", "http://ping-agent:8080/metrics"
)
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "").strip()
PROMETHEUS_QUERY_CACHE_SECONDS = int(
    os.getenv("PROMETHEUS_QUERY_CACHE_SECONDS", "15")
)
_PROM_CACHE: dict[str, tuple[float, dict[str, float]]] = {}
_PROM_CACHE_LOCK = threading.Lock()

# Configure session with retry logic and connection pooling
SESSION = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"],
)
adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=10,
    pool_maxsize=20,
)
SESSION.mount("http://", adapter)
SESSION.mount("https://", adapter)
DEFAULT_TARGETS = ["https://google.com", "https://github.com"]
targets_env = os.getenv("PING_TARGET_URLS", "").strip()
if targets_env:
    MONITORED_TARGETS = [t.strip() for t in targets_env.split(",") if t.strip()]
else:
    MONITORED_TARGETS = DEFAULT_TARGETS

REQUEST_COUNT = Counter(
    "api_gateway_requests_total",
    "Total HTTP requests received by api-gateway",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "api_gateway_request_duration_seconds",
    "Request latency in seconds for api-gateway",
    ["method", "path"],
)


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status=str(response.status_code),
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        path=request.url.path,
    ).observe(duration)
    return response


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/targets")
def targets() -> dict[str, list[dict[str, str]]]:
    return {"targets": [{"url": url} for url in MONITORED_TARGETS]}


def _parse_counter_by_target(metrics_text: str, metric_name: str) -> dict[str, float]:
    results: dict[str, float] = {}
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        name_end = line.find("{")
        if name_end == -1:
            name_end = line.find(" ")
        if name_end == -1:
            continue
        if line[:name_end] != metric_name:
            continue
        if "{" not in line or "}" not in line:
            continue
        labels_part, value_part = line.split("}", 1)
        labels_part = labels_part.split("{", 1)[-1]
        match = re.search(r'target="([^"]+)"', labels_part)
        if not match:
            continue
        target = match.group(1)
        value_fields = value_part.strip().split()
        if not value_fields:
            continue
        try:
            results[target] = float(value_fields[0])
        except ValueError:
            continue
    return results


def _parse_prometheus_vector_by_target(payload: dict) -> dict[str, float]:
    results: dict[str, float] = {}
    data = payload.get("data", {})
    for entry in data.get("result", []):
        labels = entry.get("metric", {})
        target = labels.get("target")
        value = entry.get("value", [])
        if not target or len(value) < 2:
            continue
        try:
            results[target] = float(value[1])
        except (TypeError, ValueError):
            continue
    return results


def _query_prometheus_increase(metric_name: str, window: str) -> dict[str, float]:
    cache_key = f"{metric_name}:{window}"
    if PROMETHEUS_QUERY_CACHE_SECONDS > 0:
        cached = _get_cache(cache_key)
        if cached is not None:
            return cached
    if not PROMETHEUS_URL:
        raise ValueError("PROMETHEUS_URL is not configured")
    query = f"sum by (target) (increase({metric_name}[{window}]))"
    try:
        response = SESSION.get(
            f"{PROMETHEUS_URL.rstrip('/')}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            error_msg = payload.get("error", {}).get("message", "Unknown error")
            raise ValueError(f"Prometheus query failed: {error_msg}")
        results = _parse_prometheus_vector_by_target(payload)
        if PROMETHEUS_QUERY_CACHE_SECONDS > 0:
            _set_cache(cache_key, results)
        return results
    except requests.RequestException as exc:
        raise ValueError(f"Failed to query Prometheus: {exc}") from exc


def _get_cache(key: str) -> dict[str, float] | None:
    now = time.monotonic()
    with _PROM_CACHE_LOCK:
        cached = _PROM_CACHE.get(key)
        if not cached:
            return None
        timestamp, value = cached
        if now - timestamp > PROMETHEUS_QUERY_CACHE_SECONDS:
            _PROM_CACHE.pop(key, None)
            return None
        return value


def _set_cache(key: str, value: dict[str, float]) -> None:
    with _PROM_CACHE_LOCK:
        _PROM_CACHE[key] = (time.monotonic(), value)


@app.get("/uptime-summary")
def uptime_summary() -> dict[str, list[dict[str, object]]]:
    try:
        response = SESSION.get(PING_AGENT_METRICS_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch ping-agent metrics: {exc}") from exc

    metrics_text = response.text
    if not metrics_text:
        raise HTTPException(status_code=502, detail="Empty response from ping-agent")
    
    success_by_target = _parse_counter_by_target(metrics_text, "ping_success_total")
    failures_by_target = _parse_counter_by_target(metrics_text, "ping_failure_total")

    results = []
    for target in MONITORED_TARGETS:
        success = success_by_target.get(target, 0.0)
        failures = failures_by_target.get(target, 0.0)
        total = success + failures
        availability = (success / total) * 100 if total > 0 else 0.0
        results.append(
            {
                "url": target,
                "success": success,
                "failures": failures,
                "availability": f"{availability:.0f}%",
            }
        )

    return {"targets": results}


@app.get("/uptime-summary-windowed")
def uptime_summary_windowed(window: str = "5m") -> dict[str, object]:
    if not PROMETHEUS_URL:
        raise HTTPException(status_code=501, detail="PROMETHEUS_URL is not configured")
    try:
        success_by_target = _query_prometheus_increase("ping_success_total", window)
        failures_by_target = _query_prometheus_increase("ping_failure_total", window)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results = []
    for target in MONITORED_TARGETS:
        success = success_by_target.get(target, 0.0)
        failures = failures_by_target.get(target, 0.0)
        total = success + failures
        availability = (success / total) * 100 if total > 0 else 0.0
        results.append(
            {
                "url": target,
                "success": success,
                "failures": failures,
                "availability": f"{availability:.0f}%",
            }
        )

    return {"window": window, "targets": results}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def get_service_Status() -> dict[str, str]:
    return {"service": "ping-agent", "uptime": "99.99%", "latency": "123ms"}
