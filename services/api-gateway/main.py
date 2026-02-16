import math
import os
import re
import threading
import time
from urllib.parse import unquote

import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
app = FastAPI(
    title="iYup API",
    description="Uptime and latency monitoring API",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_methods=["GET"],
    allow_headers=["*"],
)

WINDOW_PATTERN = re.compile(r"^\d+[smhdw]$")


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
    """
    Parse Prometheus counter metrics by target label.
    
    Handles formats like:
    - metric_name{target="url"} value
    - metric_name{target="url"} value timestamp
    - metric_name{target="url",other="label"} value
    """
    results: dict[str, float] = {}
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Find metric name end (either at { or space)
        name_end = line.find("{")
        if name_end == -1:
            name_end = line.find(" ")
        if name_end == -1:
            continue
        
        # Check if this line matches the metric we're looking for
        if line[:name_end] != metric_name:
            continue
        
        # Must have labels in { } format
        if "{" not in line or "}" not in line:
            continue
        
        # Split labels and value parts
        labels_part, value_part = line.split("}", 1)
        labels_part = labels_part.split("{", 1)[-1]
        
        # Extract target from labels
        match = re.search(r'target="([^"]+)"', labels_part)
        if not match:
            continue
        
        target = match.group(1)
        if not target:
            continue
        
        # Parse value (first field, ignore timestamp if present)
        value_fields = value_part.strip().split()
        if not value_fields:
            continue
        
        try:
            value = float(value_fields[0])
            # Validate value is non-negative (counters should never be negative)
            if value < 0:
                continue
            # If target already exists, keep the larger value (shouldn't happen, but handle gracefully)
            if target in results:
                results[target] = max(results[target], value)
            else:
                results[target] = value
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
    metrics_text = _fetch_ping_metrics()
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
                "availability": f"{availability:.2f}%",
            }
        )

    return {"targets": results}


@app.get("/uptime-summary-windowed")
def uptime_summary_windowed(window: str = "5m") -> dict[str, object]:
    if not WINDOW_PATTERN.match(window):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid window format '{window}'. Use a number followed by s/m/h/d/w (e.g. 5m, 1h, 24h, 7d).",
        )
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
                "availability": f"{availability:.2f}%",
            }
        )

    return {"window": window, "targets": results}


def _parse_gauge_by_target(metrics_text: str, metric_name: str) -> dict[str, float]:
    """Parse a Prometheus gauge metric by target label."""
    results: dict[str, float] = {}
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name_end = line.find("{")
        if name_end == -1:
            continue
        if line[:name_end] != metric_name:
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


def _parse_histogram_by_target(
    metrics_text: str,
) -> dict[str, list[tuple[float, float]]]:
    """Parse ping_latency_seconds histogram buckets into {target: [(le, count)]}."""
    buckets: dict[str, list[tuple[float, float]]] = {}
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("ping_latency_seconds_bucket{"):
            continue
        labels_part, value_part = line.split("}", 1)
        labels_part = labels_part.split("{", 1)[-1]
        target_match = re.search(r'target="([^"]+)"', labels_part)
        le_match = re.search(r'le="([^"]+)"', labels_part)
        if not target_match or not le_match:
            continue
        target = target_match.group(1)
        le_str = le_match.group(1)
        value_fields = value_part.strip().split()
        if not value_fields:
            continue
        try:
            le = float(le_str) if le_str != "+Inf" else math.inf
            count = float(value_fields[0])
        except ValueError:
            continue
        buckets.setdefault(target, []).append((le, count))
    for target in buckets:
        buckets[target].sort(key=lambda x: x[0])
    return buckets


def _percentile_from_histogram(
    bucket_list: list[tuple[float, float]], percentile: float
) -> float | None:
    """Estimate a percentile from sorted histogram buckets [(le, cumulative_count)]."""
    if not bucket_list:
        return None
    total = bucket_list[-1][1]
    if total == 0:
        return None
    threshold = total * percentile
    prev_le = 0.0
    prev_count = 0.0
    for le, count in bucket_list:
        if le == math.inf:
            break
        if count >= threshold:
            # Linear interpolation within the bucket
            bucket_width = le - prev_le
            bucket_count = count - prev_count
            if bucket_count == 0:
                return le
            fraction = (threshold - prev_count) / bucket_count
            return prev_le + fraction * bucket_width
        prev_le = le
        prev_count = count
    # Above all finite buckets
    finite = [(le, c) for le, c in bucket_list if le != math.inf]
    return finite[-1][0] if finite else None


def _latency_percentiles(
    bucket_list: list[tuple[float, float]],
) -> dict[str, float | None]:
    return {
        "p50": _percentile_from_histogram(bucket_list, 0.50),
        "p95": _percentile_from_histogram(bucket_list, 0.95),
        "p99": _percentile_from_histogram(bucket_list, 0.99),
    }


def _fetch_ping_metrics() -> str:
    """Fetch raw metrics text from ping-agent."""
    try:
        response = SESSION.get(PING_AGENT_METRICS_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch ping-agent metrics: {exc}"
        ) from exc
    if not response.text:
        raise HTTPException(status_code=502, detail="Empty response from ping-agent")
    return response.text


def _ms(val: float | None) -> float | None:
    """Convert seconds to milliseconds, rounded."""
    return round(val * 1000, 2) if val is not None else None


@app.get("/status")
def status():
    """Real-time status of all monitored targets."""
    metrics_text = _fetch_ping_metrics()

    up_by_target = _parse_gauge_by_target(metrics_text, "ping_up")
    latency_by_target = _parse_gauge_by_target(metrics_text, "ping_last_latency_seconds")
    ssl_by_target = _parse_gauge_by_target(metrics_text, "ping_ssl_cert_expiry_days")
    dns_by_target = _parse_gauge_by_target(metrics_text, "ping_dns_duration_seconds")
    connect_by_target = _parse_gauge_by_target(metrics_text, "ping_connect_duration_seconds")
    tls_by_target = _parse_gauge_by_target(metrics_text, "ping_tls_duration_seconds")
    success_by_target = _parse_counter_by_target(metrics_text, "ping_success_total")
    failures_by_target = _parse_counter_by_target(metrics_text, "ping_failure_total")
    histogram_by_target = _parse_histogram_by_target(metrics_text)

    all_up = True
    targets_status = []
    for target in MONITORED_TARGETS:
        is_up = up_by_target.get(target, 0.0) == 1.0
        if not is_up:
            all_up = False
        last_latency = latency_by_target.get(target)
        success = success_by_target.get(target, 0.0)
        failures = failures_by_target.get(target, 0.0)
        total = success + failures
        availability = (success / total) * 100 if total > 0 else 0.0
        latency_p = _latency_percentiles(histogram_by_target.get(target, []))

        ssl_days = ssl_by_target.get(target)
        dns_ms = _ms(dns_by_target.get(target))
        tcp_ms = _ms(connect_by_target.get(target))
        tls_ms = _ms(tls_by_target.get(target))

        entry: dict[str, object] = {
            "url": target,
            "up": is_up,
            "latency_ms": round(last_latency * 1000, 1) if last_latency is not None else None,
            "availability": round(availability, 2),
            "total_checks": int(total),
            "latency_percentiles_ms": {
                k: round(v * 1000, 1) if v is not None else None
                for k, v in latency_p.items()
            },
            "connection_ms": {"dns": dns_ms, "tcp": tcp_ms, "tls": tls_ms},
        }
        if ssl_days is not None:
            entry["ssl_cert_expiry_days"] = round(ssl_days, 1)
        targets_status.append(entry)

    overall = "operational" if all_up else "degraded"
    return {
        "status": overall,
        "targets": targets_status,
    }


@app.get("/targets/{target_url:path}")
def target_detail(target_url: str):
    """Detailed metrics for a single target."""
    target_url = unquote(target_url)
    if target_url not in MONITORED_TARGETS:
        raise HTTPException(status_code=404, detail=f"Target '{target_url}' is not monitored")

    metrics_text = _fetch_ping_metrics()

    up_by_target = _parse_gauge_by_target(metrics_text, "ping_up")
    latency_by_target = _parse_gauge_by_target(metrics_text, "ping_last_latency_seconds")
    ssl_by_target = _parse_gauge_by_target(metrics_text, "ping_ssl_cert_expiry_days")
    dns_by_target = _parse_gauge_by_target(metrics_text, "ping_dns_duration_seconds")
    connect_by_target = _parse_gauge_by_target(metrics_text, "ping_connect_duration_seconds")
    tls_by_target = _parse_gauge_by_target(metrics_text, "ping_tls_duration_seconds")
    success_by_target = _parse_counter_by_target(metrics_text, "ping_success_total")
    failures_by_target = _parse_counter_by_target(metrics_text, "ping_failure_total")
    histogram_by_target = _parse_histogram_by_target(metrics_text)

    is_up = up_by_target.get(target_url, 0.0) == 1.0
    last_latency = latency_by_target.get(target_url)
    ssl_days = ssl_by_target.get(target_url)
    success = success_by_target.get(target_url, 0.0)
    failures = failures_by_target.get(target_url, 0.0)
    total = success + failures
    availability = (success / total) * 100 if total > 0 else 0.0
    latency_p = _latency_percentiles(histogram_by_target.get(target_url, []))

    result: dict[str, object] = {
        "url": target_url,
        "up": is_up,
        "latency_ms": round(last_latency * 1000, 1) if last_latency is not None else None,
        "availability": round(availability, 2),
        "total_checks": int(total),
        "success": int(success),
        "failures": int(failures),
        "latency_percentiles_ms": {
            k: round(v * 1000, 1) if v is not None else None
            for k, v in latency_p.items()
        },
        "connection_ms": {
            "dns": _ms(dns_by_target.get(target_url)),
            "tcp": _ms(connect_by_target.get(target_url)),
            "tls": _ms(tls_by_target.get(target_url)),
        },
    }
    if ssl_days is not None:
        result["ssl_cert_expiry_days"] = round(ssl_days, 1)
    return result
