import http.server
import importlib
import math
import os
import sys
import threading
import unittest
from unittest.mock import Mock, patch

import requests

API_DIR = os.path.dirname(__file__)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

TEST_TARGETS = ["https://a", "https://b"]
REAL_TARGETS = ["https://google.com", "https://github.com"]
TEST_TARGETS_CSV = ",".join(TEST_TARGETS)
TEST_EXTRA_TARGET = "https://c"
TEST_PROM_URL = "http://prom.example"

os.environ["PING_TARGET_URLS"] = TEST_TARGETS_CSV
main = importlib.import_module("main")


FULL_METRICS_TEXT = "\n".join(
    [
        '# HELP ping_success_total Total successful pings',
        '# TYPE ping_success_total counter',
        'ping_success_total{target="https://a"} 90',
        'ping_success_total{target="https://b"} 50',
        '# HELP ping_failure_total Total failed pings',
        '# TYPE ping_failure_total counter',
        'ping_failure_total{target="https://a"} 10',
        'ping_failure_total{target="https://b"} 50',
        '# HELP ping_up Current target status',
        '# TYPE ping_up gauge',
        'ping_up{target="https://a"} 1',
        'ping_up{target="https://b"} 0',
        '# HELP ping_last_latency_seconds Last ping latency',
        '# TYPE ping_last_latency_seconds gauge',
        'ping_last_latency_seconds{target="https://a"} 0.045',
        'ping_last_latency_seconds{target="https://b"} 1.200',
        '# HELP ping_latency_seconds Latency histogram',
        '# TYPE ping_latency_seconds histogram',
        'ping_latency_seconds_bucket{target="https://a",le="0.005"} 0',
        'ping_latency_seconds_bucket{target="https://a",le="0.01"} 0',
        'ping_latency_seconds_bucket{target="https://a",le="0.025"} 10',
        'ping_latency_seconds_bucket{target="https://a",le="0.05"} 60',
        'ping_latency_seconds_bucket{target="https://a",le="0.1"} 90',
        'ping_latency_seconds_bucket{target="https://a",le="0.25"} 95',
        'ping_latency_seconds_bucket{target="https://a",le="0.5"} 98',
        'ping_latency_seconds_bucket{target="https://a",le="1"} 100',
        'ping_latency_seconds_bucket{target="https://a",le="2.5"} 100',
        'ping_latency_seconds_bucket{target="https://a",le="5"} 100',
        'ping_latency_seconds_bucket{target="https://a",le="10"} 100',
        'ping_latency_seconds_bucket{target="https://a",le="+Inf"} 100',
    ]
)


class TestMetricsParsing(unittest.TestCase):
    def test_parse_counter_by_target(self):
        metrics_text = "\n".join(
            [
                f'ping_success_total{{target="{TEST_TARGETS[0]}"}} 12',
                f'ping_success_total{{target="{TEST_TARGETS[1]}"}} 0',
                f'ping_success_total{{target="{TEST_EXTRA_TARGET}"}} 4',
                f'ping_success_total_created{{target="{TEST_TARGETS[0]}"}} 9999',
                f'ping_failure_total{{target="{TEST_TARGETS[0]}"}} 1',
                "ping_success_total 99",
                'ping_success_total{badlabel="x"} 3',
            ]
        )
        results = main._parse_counter_by_target(metrics_text, "ping_success_total")
        self.assertEqual(results[TEST_TARGETS[0]], 12.0)
        self.assertEqual(results[TEST_TARGETS[1]], 0.0)
        self.assertEqual(results[TEST_EXTRA_TARGET], 4.0)
        self.assertNotIn("ping_success_total", results)

    def test_parse_gauge_by_target(self):
        metrics_text = "\n".join(
            [
                'ping_up{target="https://a"} 1',
                'ping_up{target="https://b"} 0',
                'ping_last_latency_seconds{target="https://a"} 0.045',
            ]
        )
        up = main._parse_gauge_by_target(metrics_text, "ping_up")
        self.assertEqual(up["https://a"], 1.0)
        self.assertEqual(up["https://b"], 0.0)

        latency = main._parse_gauge_by_target(metrics_text, "ping_last_latency_seconds")
        self.assertAlmostEqual(latency["https://a"], 0.045)

    def test_parse_histogram_by_target(self):
        buckets = main._parse_histogram_by_target(FULL_METRICS_TEXT)
        self.assertIn("https://a", buckets)
        a_buckets = buckets["https://a"]
        # Should have 12 buckets (including +Inf)
        self.assertEqual(len(a_buckets), 12)
        # Should be sorted by le
        les = [le for le, _ in a_buckets]
        self.assertEqual(les, sorted(les))


class TestLatencyPercentiles(unittest.TestCase):
    def test_percentile_from_histogram(self):
        # 100 samples: 10 in 0.01-0.025, 50 in 0.025-0.05, 30 in 0.05-0.1, etc.
        bucket_list = [
            (0.005, 0),
            (0.01, 0),
            (0.025, 10),
            (0.05, 60),
            (0.1, 90),
            (0.25, 95),
            (0.5, 98),
            (1.0, 100),
            (math.inf, 100),
        ]
        p50 = main._percentile_from_histogram(bucket_list, 0.50)
        p95 = main._percentile_from_histogram(bucket_list, 0.95)
        p99 = main._percentile_from_histogram(bucket_list, 0.99)
        # p50 should be within the 0.025-0.05 bucket
        self.assertIsNotNone(p50)
        self.assertGreater(p50, 0.025)
        self.assertLessEqual(p50, 0.05)
        # p95 should be in the 0.1-0.25 bucket
        self.assertIsNotNone(p95)
        self.assertGreater(p95, 0.1)
        self.assertLessEqual(p95, 0.25)
        # p99 should be in the 0.25-0.5 bucket
        self.assertIsNotNone(p99)

    def test_percentile_empty(self):
        self.assertIsNone(main._percentile_from_histogram([], 0.50))

    def test_percentile_zero_total(self):
        bucket_list = [(0.1, 0), (0.5, 0), (math.inf, 0)]
        self.assertIsNone(main._percentile_from_histogram(bucket_list, 0.50))


class TestUptimeSummary(unittest.TestCase):
    def test_uptime_summary(self):
        mock_response = Mock()
        mock_response.text = "\n".join(
            [
                f'ping_success_total{{target="{TEST_TARGETS[0]}"}} 5',
                f'ping_failure_total{{target="{TEST_TARGETS[0]}"}} 5',
                f'ping_success_total{{target="{TEST_TARGETS[1]}"}} 10',
                f'ping_failure_total{{target="{TEST_TARGETS[1]}"}} 0',
            ]
        )
        mock_response.raise_for_status = Mock()

        with patch.object(main.SESSION, "get", return_value=mock_response):
            payload = main.uptime_summary()

        self.assertEqual(len(payload["targets"]), 2)
        self.assertEqual(payload["targets"][0]["availability"], "50.00%")
        self.assertEqual(payload["targets"][1]["availability"], "100.00%")


class TestUptimeSummaryIntegration(unittest.TestCase):
    def test_uptime_summary_against_fake_metrics(self):
        metrics_payload = "\n".join(
            [
                f'ping_success_total{{target="{TEST_TARGETS[0]}"}} 3',
                f'ping_failure_total{{target="{TEST_TARGETS[0]}"}} 1',
                f'ping_success_total{{target="{TEST_TARGETS[1]}"}} 2',
                f'ping_failure_total{{target="{TEST_TARGETS[1]}"}} 2',
            ]
        )

        class MetricsHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/metrics":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = metrics_payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args, **_kwargs):
                return

        try:
            server = http.server.HTTPServer(("127.0.0.1", 0), MetricsHandler)
        except (OSError, PermissionError) as e:
            self.skipTest(f"Cannot create test server (permissions/network): {e}")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            main.PING_AGENT_METRICS_URL = (
                f"http://127.0.0.1:{server.server_port}/metrics"
            )
            main.MONITORED_TARGETS = TEST_TARGETS
            payload = main.uptime_summary()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

        self.assertEqual(payload["targets"][0]["availability"], "75.00%")
        self.assertEqual(payload["targets"][1]["availability"], "50.00%")


class TestStatusEndpoint(unittest.TestCase):
    def test_status_returns_real_data(self):
        mock_response = Mock()
        mock_response.text = FULL_METRICS_TEXT
        mock_response.raise_for_status = Mock()

        with patch.object(main.SESSION, "get", return_value=mock_response):
            main.MONITORED_TARGETS = TEST_TARGETS
            payload = main.status()

        self.assertIn("status", payload)
        self.assertIn(payload["status"], ("operational", "degraded"))
        # Target a is up, target b is down → degraded
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(len(payload["targets"]), 2)

        target_a = payload["targets"][0]
        self.assertTrue(target_a["up"])
        self.assertAlmostEqual(target_a["latency_ms"], 45.0)
        self.assertAlmostEqual(target_a["availability"], 90.0)
        self.assertEqual(target_a["total_checks"], 100)
        self.assertIn("p50", target_a["latency_percentiles_ms"])
        self.assertIn("p95", target_a["latency_percentiles_ms"])
        self.assertIn("p99", target_a["latency_percentiles_ms"])

        target_b = payload["targets"][1]
        self.assertFalse(target_b["up"])

    def test_status_all_up(self):
        metrics_text = "\n".join(
            [
                'ping_up{target="https://a"} 1',
                'ping_up{target="https://b"} 1',
                'ping_last_latency_seconds{target="https://a"} 0.05',
                'ping_last_latency_seconds{target="https://b"} 0.03',
                'ping_success_total{target="https://a"} 10',
                'ping_success_total{target="https://b"} 10',
                'ping_failure_total{target="https://a"} 0',
                'ping_failure_total{target="https://b"} 0',
            ]
        )
        mock_response = Mock()
        mock_response.text = metrics_text
        mock_response.raise_for_status = Mock()

        with patch.object(main.SESSION, "get", return_value=mock_response):
            main.MONITORED_TARGETS = TEST_TARGETS
            payload = main.status()

        self.assertEqual(payload["status"], "operational")


class TestTargetDetailEndpoint(unittest.TestCase):
    def test_target_detail(self):
        mock_response = Mock()
        mock_response.text = FULL_METRICS_TEXT
        mock_response.raise_for_status = Mock()

        with patch.object(main.SESSION, "get", return_value=mock_response):
            main.MONITORED_TARGETS = TEST_TARGETS
            payload = main.target_detail("https://a")

        self.assertEqual(payload["url"], "https://a")
        self.assertTrue(payload["up"])
        self.assertEqual(payload["success"], 90)
        self.assertEqual(payload["failures"], 10)
        self.assertAlmostEqual(payload["availability"], 90.0)
        self.assertIn("latency_percentiles_ms", payload)

    def test_target_not_found(self):
        main.MONITORED_TARGETS = TEST_TARGETS
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            main.target_detail("https://unknown.com")
        self.assertEqual(ctx.exception.status_code, 404)


class TestWindowValidation(unittest.TestCase):
    def test_valid_windows(self):
        for w in ["5m", "1h", "24h", "7d", "30s", "2w"]:
            self.assertTrue(main.WINDOW_PATTERN.match(w), f"{w} should be valid")

    def test_invalid_windows(self):
        for w in ["abc", "5mm", "1", "m5", "", "5m; drop table", "5m\n1h"]:
            self.assertFalse(main.WINDOW_PATTERN.match(w), f"{w} should be invalid")

    def test_windowed_rejects_bad_window(self):
        main.PROMETHEUS_URL = TEST_PROM_URL
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            main.uptime_summary_windowed(window="invalid")
        self.assertEqual(ctx.exception.status_code, 400)


class TestPrometheusWindowed(unittest.TestCase):
    def test_parse_prometheus_vector_by_target(self):
        payload = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {"metric": {"target": TEST_TARGETS[0]}, "value": [123, "5"]},
                    {"metric": {"target": TEST_TARGETS[1]}, "value": [123, "2"]},
                    {"metric": {"job": "ping"}, "value": [123, "1"]},
                ],
            },
        }
        results = main._parse_prometheus_vector_by_target(payload)
        self.assertEqual(results, {TEST_TARGETS[0]: 5.0, TEST_TARGETS[1]: 2.0})

    def test_uptime_summary_windowed(self):
        main.PROMETHEUS_URL = TEST_PROM_URL

        def fake_get(url, params=None, timeout=None):
            query = (params or {}).get("query", "")
            mock_response = Mock()
            if "ping_success_total" in query:
                mock_response.json = Mock(
                    return_value={
                        "status": "success",
                        "data": {
                            "result": [
                                {"metric": {"target": TEST_TARGETS[0]}, "value": [0, "3"]},
                                {"metric": {"target": TEST_TARGETS[1]}, "value": [0, "2"]},
                            ]
                        },
                    }
                )
            else:
                mock_response.json = Mock(
                    return_value={
                        "status": "success",
                        "data": {
                            "result": [
                                {"metric": {"target": TEST_TARGETS[0]}, "value": [0, "1"]},
                                {"metric": {"target": TEST_TARGETS[1]}, "value": [0, "2"]},
                            ]
                        },
                    }
                )
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch.object(main.SESSION, "get", side_effect=fake_get):
            main.MONITORED_TARGETS = TEST_TARGETS
            payload = main.uptime_summary_windowed(window="5m")

        self.assertEqual(payload["window"], "5m")
        self.assertEqual(payload["targets"][0]["availability"], "75.00%")
        self.assertEqual(payload["targets"][1]["availability"], "50.00%")

    def test_prometheus_query_cache(self):
        main.PROMETHEUS_URL = TEST_PROM_URL
        previous_ttl = main.PROMETHEUS_QUERY_CACHE_SECONDS
        previous_cache = main._PROM_CACHE
        main.PROMETHEUS_QUERY_CACHE_SECONDS = 60
        main._PROM_CACHE = {}
        call_count = {"count": 0}

        def fake_get(_url, params=None, timeout=None):
            call_count["count"] += 1
            query = (params or {}).get("query", "")
            mock_response = Mock()
            if "ping_success_total" in query:
                mock_response.json = Mock(
                    return_value={
                        "status": "success",
                        "data": {
                            "result": [
                                {"metric": {"target": TEST_TARGETS[0]}, "value": [0, "3"]}
                            ]
                        },
                    }
                )
            else:
                mock_response.json = Mock(return_value={"status": "success", "data": {"result": []}})
            mock_response.raise_for_status = Mock()
            return mock_response

        try:
            with patch.object(main.SESSION, "get", side_effect=fake_get):
                first = main._query_prometheus_increase("ping_success_total", "5m")
                second = main._query_prometheus_increase("ping_success_total", "5m")
        finally:
            main.PROMETHEUS_QUERY_CACHE_SECONDS = previous_ttl
            main._PROM_CACHE = previous_cache

        self.assertEqual(call_count["count"], 1)
        self.assertEqual(first, second)


class TestRealTargetsIntegration(unittest.TestCase):
    """Integration tests that ping real targets: google.com and github.com"""

    def test_google_com_reachable(self):
        try:
            response = requests.get(REAL_TARGETS[0], timeout=10)
            self.assertLess(response.status_code, 400, "google.com should return success status")
        except (requests.RequestException, OSError) as e:
            self.skipTest(f"Network unavailable or google.com unreachable: {e}")

    def test_github_com_reachable(self):
        try:
            response = requests.get(REAL_TARGETS[1], timeout=10)
            self.assertLess(response.status_code, 400, "github.com should return success status")
        except (requests.RequestException, OSError) as e:
            self.skipTest(f"Network unavailable or github.com unreachable: {e}")

    def test_default_targets_include_google_and_github(self):
        self.assertIn(REAL_TARGETS[0], main.DEFAULT_TARGETS)
        self.assertIn(REAL_TARGETS[1], main.DEFAULT_TARGETS)
