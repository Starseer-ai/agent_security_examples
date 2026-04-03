#!/usr/bin/env python3
"""
Verbose HTTP Request Logger

A simple HTTP server that logs every incoming request in detail, including
the method, path, query parameters, headers, and body content. Useful for
observing what web requests other systems send to a given address.

Usage:
    python3 request_logger.py [--host HOST] [--port PORT]

Examples:
    python3 request_logger.py --host 127.0.0.1 --port 3000
    python3 request_logger.py --port 8080
"""

import argparse
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class RequestLoggerHandler(BaseHTTPRequestHandler):
    """HTTP request handler that logs all request details to stdout."""

    def _log_request(self):
        """Read and log every detail of the incoming request."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        # Read body if Content-Length is present
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # Build the log output
        separator = "=" * 72
        lines = [
            "",
            separator,
            f"  REQUEST RECEIVED — {timestamp}",
            separator,
            f"  Client:  {self.client_address[0]}:{self.client_address[1]}",
            f"  Method:  {self.command}",
            f"  Path:    {parsed.path}",
            f"  HTTP:    {self.request_version}",
        ]

        # Query parameters
        if query_params:
            lines.append("")
            lines.append("  QUERY PARAMETERS:")
            for key, values in query_params.items():
                for value in values:
                    lines.append(f"    {key} = {value}")
        elif parsed.query:
            # Raw query string that didn't parse cleanly
            lines.append("")
            lines.append(f"  QUERY STRING (raw): {parsed.query}")

        # Headers
        lines.append("")
        lines.append("  HEADERS:")
        for header, value in self.headers.items():
            lines.append(f"    {header}: {value}")

        # Body
        lines.append("")
        lines.append(f"  BODY ({content_length} bytes):")
        if body:
            try:
                decoded = body.decode("utf-8")
                # Indent each line of the body for readability
                for body_line in decoded.splitlines():
                    lines.append(f"    {body_line}")
            except UnicodeDecodeError:
                lines.append(f"    <binary data, {content_length} bytes>")
                lines.append(f"    hex: {body[:256].hex()}")
                if content_length > 256:
                    lines.append(f"    ... ({content_length - 256} more bytes)")
        else:
            lines.append("    <empty>")

        lines.append(separator)
        lines.append("")

        print("\n".join(lines), flush=True)

        # Send a simple 200 OK response
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK\n")

    # Route every HTTP method through the same logging handler
    def do_GET(self):
        self._log_request()

    def do_POST(self):
        self._log_request()

    def do_PUT(self):
        self._log_request()

    def do_DELETE(self):
        self._log_request()

    def do_PATCH(self):
        self._log_request()

    def do_HEAD(self):
        self._log_request()

    def do_OPTIONS(self):
        self._log_request()

    def log_message(self, format, *args):
        """Suppress the default stderr access log since we handle logging ourselves."""
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Verbose HTTP request logger — logs all incoming requests to stdout."
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), RequestLoggerHandler)
    print(f"Request logger listening on {args.host}:{args.port}")
    print("Press Ctrl+C to stop.\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()
