import http.server
import importlib
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
        self.assertEqual(
            payload["targets"][0],
            {
                "url": TEST_TARGETS[0],
                "success": 5.0,
                "failures": 5.0,
                "availability": "50%",
            },
        )
        self.assertEqual(
            payload["targets"][1],
            {
                "url": TEST_TARGETS[1],
                "success": 10.0,
                "failures": 0.0,
                "availability": "100%",
            },
        )


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

        self.assertEqual(
            payload,
            {
                "targets": [
                    {
                        "url": TEST_TARGETS[0],
                        "success": 3.0,
                        "failures": 1.0,
                        "availability": "75%",
                    },
                    {
                        "url": TEST_TARGETS[1],
                        "success": 2.0,
                        "failures": 2.0,
                        "availability": "50%",
                    },
                ]
            },
        )


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

        self.assertEqual(
            payload,
            {
                "window": "5m",
                "targets": [
                    {
                        "url": TEST_TARGETS[0],
                        "success": 3.0,
                        "failures": 1.0,
                        "availability": "75%",
                    },
                    {
                        "url": TEST_TARGETS[1],
                        "success": 2.0,
                        "failures": 2.0,
                        "availability": "50%",
                    },
                ],
            },
        )

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
        """Test that google.com is reachable and returns 2xx/3xx status"""
        try:
            response = requests.get(REAL_TARGETS[0], timeout=10)
            self.assertLess(response.status_code, 400, "google.com should return success status")
        except (requests.RequestException, OSError) as e:
            self.skipTest(f"Network unavailable or google.com unreachable: {e}")

    def test_github_com_reachable(self):
        """Test that github.com is reachable and returns 2xx/3xx status"""
        try:
            response = requests.get(REAL_TARGETS[1], timeout=10)
            self.assertLess(response.status_code, 400, "github.com should return success status")
        except (requests.RequestException, OSError) as e:
            self.skipTest(f"Network unavailable or github.com unreachable: {e}")

    def test_parse_counter_with_real_target_urls(self):
        """Test parsing metrics with real target URLs (google.com, github.com)"""
        metrics_text = "\n".join(
            [
                f'ping_success_total{{target="{REAL_TARGETS[0]}"}} 100',
                f'ping_success_total{{target="{REAL_TARGETS[1]}"}} 95',
                f'ping_failure_total{{target="{REAL_TARGETS[0]}"}} 0',
                f'ping_failure_total{{target="{REAL_TARGETS[1]}"}} 5',
            ]
        )
        success = main._parse_counter_by_target(metrics_text, "ping_success_total")
        failures = main._parse_counter_by_target(metrics_text, "ping_failure_total")

        self.assertEqual(success[REAL_TARGETS[0]], 100.0)
        self.assertEqual(success[REAL_TARGETS[1]], 95.0)
        self.assertEqual(failures[REAL_TARGETS[0]], 0.0)
        self.assertEqual(failures[REAL_TARGETS[1]], 5.0)

    def test_uptime_summary_with_real_targets(self):
        """Test uptime_summary endpoint with google.com and github.com as targets"""
        mock_response = Mock()
        mock_response.text = "\n".join(
            [
                f'ping_success_total{{target="{REAL_TARGETS[0]}"}} 99',
                f'ping_failure_total{{target="{REAL_TARGETS[0]}"}} 1',
                f'ping_success_total{{target="{REAL_TARGETS[1]}"}} 95',
                f'ping_failure_total{{target="{REAL_TARGETS[1]}"}} 5',
            ]
        )
        mock_response.raise_for_status = Mock()

        original_targets = main.MONITORED_TARGETS
        try:
            main.MONITORED_TARGETS = REAL_TARGETS
            with patch.object(main.SESSION, "get", return_value=mock_response):
                payload = main.uptime_summary()

            self.assertEqual(len(payload["targets"]), 2)
            
            google_result = payload["targets"][0]
            self.assertEqual(google_result["url"], REAL_TARGETS[0])
            self.assertEqual(google_result["success"], 99.0)
            self.assertEqual(google_result["failures"], 1.0)
            self.assertEqual(google_result["availability"], "99%")

            github_result = payload["targets"][1]
            self.assertEqual(github_result["url"], REAL_TARGETS[1])
            self.assertEqual(github_result["success"], 95.0)
            self.assertEqual(github_result["failures"], 5.0)
            self.assertEqual(github_result["availability"], "95%")
        finally:
            main.MONITORED_TARGETS = original_targets

    def test_default_targets_include_google_and_github(self):
        """Verify that DEFAULT_TARGETS includes google.com and github.com"""
        self.assertIn(REAL_TARGETS[0], main.DEFAULT_TARGETS)
        self.assertIn(REAL_TARGETS[1], main.DEFAULT_TARGETS)
