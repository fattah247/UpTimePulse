# Reliability Scenarios

## Healthy endpoint

Expected:

- target is up
- latency is recorded
- metrics are exposed
- dashboard remains stable

Notes:

- verified during local Docker Compose checks in Phase 0

## Down endpoint

Expected:

- target is marked down after retry behavior
- failure count increases
- availability drops
- alert can fire if rules are enabled

Notes:

- retry logic is implemented in `ping-agent`
- Prometheus rule and Alertmanager routing path are present
- a local fault-injection run is not recorded in Phase 1, so this remains implementation-backed rather than fully re-demonstrated here

## Slow endpoint

Expected:

- target may remain up
- latency percentiles increase
- dashboard shows degradation

Notes:

- latency metrics and percentile calculations are implemented and verified on healthy targets
- a dedicated slow-target exercise is not part of the current screenshot pass

## Transient failure

Expected:

- retry and backoff reduce noisy false positives
- status should not flap immediately if retry logic is configured

Notes:

- retry behavior is implemented in `ping-agent`
- this scenario is described from the current implementation and not from a dedicated replay script

## Prometheus unavailable

Expected:

- API health remains separate from Prometheus health
- Prometheus-backed windowed data may be unavailable

Notes:

- `/healthz` is independent of Prometheus
- `/uptime-summary-windowed` depends on Prometheus and returns an upstream error when Prometheus data cannot be queried
