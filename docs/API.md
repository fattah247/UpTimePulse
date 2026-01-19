# API Reference

Complete reference for the iYup API Gateway endpoints.

## Base URL

When running locally or port-forwarded:
- Local dev: `http://localhost:8081`
- Kubernetes: `http://localhost:8080` (via port-forward)

## Endpoints

### Health Check

**GET** `/healthz`

Simple healthcheck endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

**Example:**
```bash
curl http://localhost:8080/healthz
```

---

### List Targets

**GET** `/targets`

Returns the list of monitored URLs.

**Response:**
```json
{
  "targets": [
    {"url": "https://google.com"},
    {"url": "https://github.com"}
  ]
}
```

**Example:**
```bash
curl http://localhost:8080/targets
```

---

### Uptime Summary

**GET** `/uptime-summary`

Returns success/failure counts and availability percentage for all targets. Uses lifetime counters from ping-agent metrics.

**Response:**
```json
{
  "targets": [
    {
      "url": "https://google.com",
      "success": 100.0,
      "failures": 0.0,
      "availability": "100%"
    },
    {
      "url": "https://github.com",
      "success": 95.0,
      "failures": 5.0,
      "availability": "95%"
    }
  ]
}
```

**Example:**
```bash
curl http://localhost:8080/uptime-summary | jq
```

**Note:** This endpoint reads directly from ping-agent metrics. For time-windowed availability, use `/uptime-summary-windowed`.

---

### Windowed Uptime Summary

**GET** `/uptime-summary-windowed?window=5m`

Returns availability calculated over a specific time window using Prometheus `increase()` queries. Requires `PROMETHEUS_URL` to be configured.

**Query Parameters:**
- `window` (optional, default: `5m`) - Time window (e.g., `5m`, `1h`, `24h`)

**Response:**
```json
{
  "window": "5m",
  "targets": [
    {
      "url": "https://google.com",
      "success": 10.0,
      "failures": 0.0,
      "availability": "100%"
    },
    {
      "url": "https://github.com",
      "success": 9.0,
      "failures": 1.0,
      "availability": "90%"
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8080/uptime-summary-windowed?window=1h" | jq
```

**Note:** Results are cached for 15 seconds (configurable via `PROMETHEUS_QUERY_CACHE_SECONDS`).

---

### Prometheus Metrics

**GET** `/metrics`

Returns Prometheus metrics for the API gateway itself.

**Metrics:**
- `api_gateway_requests_total` - Total HTTP requests (labeled by method, path, status)
- `api_gateway_request_duration_seconds` - Request latency histogram (labeled by method, path)

**Example:**
```bash
curl http://localhost:8080/metrics
```

---

## Error Responses

### 502 Bad Gateway

Returned when ping-agent metrics cannot be fetched.

```json
{
  "detail": "Failed to fetch ping-agent metrics: Connection refused"
}
```

### 501 Not Implemented

Returned when Prometheus URL is not configured but required.

```json
{
  "detail": "PROMETHEUS_URL is not configured"
}
```

---

## Environment Variables

### Required

- `PING_AGENT_METRICS_URL` - URL to ping-agent metrics endpoint (default: `http://ping-agent:8080/metrics`)

### Optional

- `PING_TARGET_URLS` - Comma-separated list of target URLs (default: `https://google.com,https://github.com`)
- `PROMETHEUS_URL` - Prometheus API URL (required for `/uptime-summary-windowed`)
- `PROMETHEUS_QUERY_CACHE_SECONDS` - Cache TTL for Prometheus queries (default: `15`)

---

## Rate Limiting

Currently, there is no rate limiting. The API gateway uses connection pooling and retry logic for reliability.

## Related Documentation

- [Quickstart Guide](QUICKSTART.md) - Getting started with the API
- [Deployment Guide](DEPLOYMENT.md) - Configuration options
- [Architecture](ARCHITECTURE.md) - System design
