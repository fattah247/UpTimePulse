# Reliability Scenarios

## Healthy endpoint

- target stays up
- latency is recorded
- metrics are exposed
- the dashboard stays stable

Verified in the local Docker Compose run.

## Down endpoint

- retry logic runs before the target is marked down
- failure count rises
- availability drops
- the alert rule can fire

This behavior is implemented. The repo does not include a recorded fault-injection replay.

## Slow endpoint

- target can stay up while latency rises
- histograms and p95 values move first
- the dashboard should show the degradation

The metrics exist. The repo does not include a dedicated slow-target capture.

## Transient failure

- retry and backoff reduce noise
- the target should not flap on the first miss

This is based on the current implementation and unit-level verification, not a replay script.

## Prometheus unavailable

- `/healthz` stays separate from Prometheus
- Prometheus-backed windowed endpoints can fail upstream

`/uptime-summary-windowed` depends on Prometheus data.
