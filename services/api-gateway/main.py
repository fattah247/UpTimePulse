import os
import re
import time

import requests
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI()


PING_AGENT_METRICS_URL = os.getenv(
    "PING_AGENT_METRICS_URL", "http://ping-agent:8080/metrics"
)
targets_env = os.getenv("PING_TARGET_URLS", "").strip()
if targets_env:
    MONITORED_TARGETS = [t.strip() for t in targets_env.split(",") if t.strip()]
else:
    MONITORED_TARGETS = [os.getenv("PING_TARGET_URL", "https://google.com")]

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
        if not line.startswith(metric_name):
            continue
        if "{" not in line or "}" not in line:
            continue
        labels_part, value_part = line.split("}", 1)
        labels_part = labels_part.split("{", 1)[-1]
        match = re.search(r'target="([^"]+)"', labels_part)
        if not match:
            continue
        target = match.group(1)
        value = value_part.strip()
        try:
            results[target] = float(value)
        except ValueError:
            continue
    return results


@app.get("/uptime-summary")
def uptime_summary() -> dict[str, list[dict[str, str | float]]]:
    try:
        response = requests.get(PING_AGENT_METRICS_URL, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    metrics_text = response.text
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def get_service_Status() -> dict[str, str]:
    return {"service": "ping-agent", "uptime": "99.99%", "latency": "123ms"}
