#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import json
import logging
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


LOGGER = logging.getLogger("gpu_http_proxy")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GPU-side local HTTP proxy backed by the shared-disk relay.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--shared-base",
        required=True,
        help="Shared directory visible to both GPU and CPU partitions.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Listen host.")
    parser.add_argument("--port", type=int, default=8317, help="Listen port.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="How long to wait for the CPU relay response.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.05,
        help="Polling interval while waiting for a response file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp_path.replace(path)


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    utf8_len = len(text.encode("utf-8"))
    char_len = len(text)
    return max(1, math.ceil(max(char_len / 4.0, utf8_len / 3.0)))


def estimate_tokens_for_value(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return estimate_text_tokens(value)
    if isinstance(value, bool):
        return 1
    if isinstance(value, (int, float)):
        return 2
    if isinstance(value, list):
        return 4 + sum(estimate_tokens_for_value(item) for item in value)
    if isinstance(value, dict):
        total = 6
        for key, item in value.items():
            total += estimate_text_tokens(str(key))
            total += estimate_tokens_for_value(item)
        return total
    return estimate_text_tokens(str(value))


def estimate_input_tokens(payload: Any) -> int:
    # Count-tokens is documented as an estimate. We intentionally bias high a bit
    # so Claude Code is less likely to under-estimate context usage.
    return max(1, int(math.ceil(estimate_tokens_for_value(payload) * 1.08)))


def make_handler(
    shared_base: Path, timeout_seconds: float, poll_interval: float
) -> type[BaseHTTPRequestHandler]:
    request_dir = shared_base / "requests"
    response_dir = shared_base / "responses"
    request_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)

    class ProxyHandler(BaseHTTPRequestHandler):
        server_version = "GpuDiskProxy/1.0"

        def do_GET(self) -> None:  # noqa: N802
            self.handle_proxy()

        def do_POST(self) -> None:  # noqa: N802
            self.handle_proxy()

        def do_PUT(self) -> None:  # noqa: N802
            self.handle_proxy()

        def do_DELETE(self) -> None:  # noqa: N802
            self.handle_proxy()

        def do_PATCH(self) -> None:  # noqa: N802
            self.handle_proxy()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.handle_proxy()

        def log_message(self, fmt: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), fmt % args)

        def handle_proxy(self) -> None:
            split = urlsplit(self.path)
            if split.path == "/health":
                self.send_json(200, {"status": "ok", "timestamp": time.time()})
                return
            if split.path == "/metrics":
                self.send_json(
                    200,
                    {
                        "pending_requests": len(list(request_dir.glob("*.json"))),
                        "pending_responses": len(list(response_dir.glob("*.json"))),
                        "timestamp": time.time(),
                    },
                )
                return
            if split.path.startswith("/api/event_logging"):
                self.send_json(200, {"success": True})
                return

            headers = self.filtered_headers()
            body = self.read_body(headers.get("content-type", ""))
            if split.path == "/v1/messages/count_tokens":
                self.send_json(200, {"input_tokens": estimate_input_tokens(body)})
                return

            request_key = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            query_params = self.normalized_query_params(split.query)
            payload = {
                "key": request_key,
                "method": self.command,
                "path": split.path or "/",
                "headers": headers,
                "query_params": query_params,
                "body": body,
                "timestamp": time.time(),
            }
            atomic_write_json(request_dir / f"{request_key}.json", payload)
            LOGGER.info("Queued %s %s as %s", self.command, split.path, request_key)

            response_file = response_dir / f"{request_key}.json"
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if response_file.exists():
                    response_payload = json.loads(
                        response_file.read_text(encoding="utf-8")
                    )
                    response_file.unlink(missing_ok=True)
                    self.write_response(response_payload)
                    return
                time.sleep(poll_interval)

            self.send_json(
                504,
                {"error": "Gateway timeout waiting for CPU relay response."},
            )

        def filtered_headers(self) -> dict[str, str]:
            result: dict[str, str] = {}
            for name, value in self.headers.items():
                if name.lower() in {
                    "host",
                    "connection",
                    "content-length",
                    "accept-encoding",
                    "authorization",
                    "x-api-key",
                }:
                    continue
                result[name] = value
            return result

        def normalized_query_params(self, query: str) -> dict[str, Any]:
            parsed = parse_qs(query, keep_blank_values=True)
            result: dict[str, Any] = {}
            for key, values in parsed.items():
                result[key] = values[0] if len(values) == 1 else values
            return result

        def read_body(self, content_type: str) -> Any:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            if "application/json" in content_type.lower():
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:  # noqa: BLE001
                    pass
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.hex()

        def write_response(self, response_payload: dict[str, Any]) -> None:
            if response_payload.get("status") == "error":
                self.send_json(
                    int(response_payload.get("status_code", 502)),
                    {
                        "error": response_payload.get("error", "Unknown relay error"),
                        "error_type": response_payload.get("error_type", "RelayError"),
                    },
                )
                return

            status_code = int(response_payload.get("status_code", 200))
            content = response_payload.get("content", "")
            content_type = response_payload.get("content_type", "application/json")
            if isinstance(content, (dict, list)):
                body = json.dumps(content, ensure_ascii=False).encode("utf-8")
            elif isinstance(content, str):
                body = content.encode("utf-8")
            else:
                body = str(content).encode("utf-8")

            self.send_response(status_code)
            headers = response_payload.get("headers") or {}
            sent_content_type = False
            for name, value in headers.items():
                lower_name = str(name).lower()
                if lower_name in {
                    "content-length",
                    "content-encoding",
                    "transfer-encoding",
                    "connection",
                    "server",
                    "date",
                }:
                    continue
                if lower_name == "content-type":
                    sent_content_type = True
                self.send_header(str(name), str(value))
            if not sent_content_type:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                LOGGER.info("Client closed connection before response write completed.")

        def send_json(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                LOGGER.info("Client closed connection before JSON response write completed.")

    return ProxyHandler


def main() -> int:
    args = parse_args()
    shared_base = Path(args.shared_base).expanduser().resolve()
    configure_logging(args.verbose)
    handler = make_handler(shared_base, args.timeout_seconds, args.poll_interval)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    LOGGER.info("Listening on http://%s:%s", args.host, args.port)
    LOGGER.info("Shared base: %s", shared_base)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user.")
        return 130
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
