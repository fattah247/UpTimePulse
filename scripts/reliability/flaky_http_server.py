#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer


class FlakyHandler(BaseHTTPRequestHandler):
    request_count = 0

    def do_GET(self) -> None:
        self._respond()

    def do_HEAD(self) -> None:
        self._respond(include_body=False)

    def log_message(self, format: str, *args) -> None:
        return

    def _respond(self, include_body: bool = True) -> None:
        FlakyHandler.request_count += 1
        if FlakyHandler.request_count == 1:
            self.send_response(503)
            self.end_headers()
            if include_body:
                self.wfile.write(b"temporary failure\n")
            return

        self.send_response(200)
        self.end_headers()
        if include_body:
            self.wfile.write(b"ok\n")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), FlakyHandler).serve_forever()
