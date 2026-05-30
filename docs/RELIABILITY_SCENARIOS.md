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

Replay:

```bash
./scripts/reliability/down-target-demo.sh
```

This replay swaps the target to `http://127.0.0.1:9`, waits for a full check cycle, and confirms that the target shows up as down.

## Slow endpoint

- target can stay up while latency rises
- histograms and p95 values move first
- the dashboard should show the degradation

The metrics exist. The repo does not include a dedicated slow-target capture.

## Transient failure

- retry and backoff reduce noise
- the target should not flap on the first miss

Replay:

```bash
./scripts/reliability/transient-target-demo.sh
```

This replay uses a helper endpoint that returns one `503` and then recovers. The final status stays up and the first miss does not leave a recorded failure.

## Prometheus unavailable

- `/healthz` stays separate from Prometheus
- Prometheus-backed windowed endpoints can fail upstream

`/uptime-summary-windowed` depends on Prometheus data.
