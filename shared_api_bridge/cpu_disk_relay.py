#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import sys
import time
import zlib
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("cpu_disk_relay")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll a shared directory and forward queued HTTP requests.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--shared-base",
        required=True,
        help="Shared directory visible to both CPU and GPU partitions.",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Online API base URL, for example https://open.bigmodel.cn/api/anthropic",
    )
    parser.add_argument(
        "--default-api-key",
        default="",
        help="Fallback API key used only when the queued request does not already carry auth.",
    )
    parser.add_argument(
        "--api-key-header",
        default="x-api-key",
        help="Header used for --default-api-key. Use Authorization to inject Bearer auth.",
    )
    parser.add_argument(
        "--auth-scheme",
        choices=("raw", "bearer"),
        default="raw",
        help="How --default-api-key should be encoded.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.1,
        help="Seconds between polling rounds when no request is pending.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=300.0,
        help="Per-request network timeout in seconds.",
    )
    parser.add_argument(
        "--response-ttl",
        type=float,
        default=3600.0,
        help="Delete response files older than this many seconds.",
    )
    parser.add_argument(
        "--idle-exit-seconds",
        type=float,
        default=0.0,
        help="Exit after being idle for this many seconds. 0 means run forever.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process the current queue once and exit.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )
    return parser.parse_args()


def configure_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers.append(logging.FileHandler(log_dir / "cpu_disk_relay.log"))
    logging.basicConfig(level=level, handlers=handlers, format=formatter._fmt)
    for handler in handlers:
        handler.setFormatter(formatter)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp_path.replace(path)


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def build_url(base_url: str, path: str, params: dict[str, Any]) -> str:
    joined = f"{base_url.rstrip('/')}{normalize_path(path)}"
    if not params:
        return joined
    query = urlencode(params, doseq=True)
    return f"{joined}?{query}"


def prepare_body(body: Any) -> tuple[bytes | None, bool]:
    if body is None:
        return None, False
    if isinstance(body, (dict, list)):
        return json.dumps(body, ensure_ascii=False).encode("utf-8"), True
    if isinstance(body, str):
        return body.encode("utf-8"), False
    return str(body).encode("utf-8"), False


def add_default_auth(headers: dict[str, str], args: argparse.Namespace) -> None:
    if not args.default_api_key:
        return
    lower_headers = {name.lower() for name in headers}
    if "authorization" in lower_headers or "x-api-key" in lower_headers:
        return
    value = args.default_api_key
    if args.api_key_header.lower() == "authorization" and args.auth_scheme == "bearer":
        value = f"Bearer {value}"
    headers[args.api_key_header] = value


def maybe_decompress(raw: bytes, content_encoding: str) -> bytes:
    encoding = content_encoding.lower().strip()
    if not encoding or encoding == "identity":
        return raw
    if "gzip" in encoding:
        return gzip.decompress(raw)
    if "deflate" in encoding:
        return zlib.decompress(raw)
    return raw


def decode_response_content(raw: bytes, content_type: str, content_encoding: str = "") -> Any:
    raw = maybe_decompress(raw, content_encoding)
    text = raw.decode("utf-8", errors="replace")
    if "json" in content_type.lower() and text.strip():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def forward_request(
    request_data: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    method = str(request_data.get("method", "GET")).upper()
    path = str(request_data.get("path", "/"))
    headers = {
        str(name): str(value)
        for name, value in (request_data.get("headers") or {}).items()
        if value is not None and str(name).lower() not in {"accept-encoding"}
    }
    add_default_auth(headers, args)
    body_bytes, body_is_json = prepare_body(request_data.get("body"))
    if body_bytes is not None and body_is_json:
        existing = {name.lower() for name in headers}
        if "content-type" not in existing:
            headers["content-type"] = "application/json"

    url = build_url(args.base_url, path, request_data.get("query_params") or {})
    request = Request(url=url, data=body_bytes, method=method)
    for name, value in headers.items():
        request.add_header(name, value)

    try:
        with urlopen(request, timeout=args.request_timeout) as response:
            raw = response.read()
            response_headers = dict(response.headers.items())
            content_type = response_headers.get("Content-Type", "application/json")
            content_encoding = response_headers.get("Content-Encoding", "")
            content = decode_response_content(raw, content_type, content_encoding)
            return {
                "status": "ok",
                "status_code": response.getcode(),
                "headers": response_headers,
                "content": content,
                "content_type": content_type,
            }
    except HTTPError as error:
        raw = error.read()
        response_headers = dict(error.headers.items())
        content_type = response_headers.get("Content-Type", "text/plain")
        content_encoding = response_headers.get("Content-Encoding", "")
        content = decode_response_content(raw, content_type, content_encoding)
        return {
            "status": "ok",
            "status_code": error.code,
            "headers": response_headers,
            "content": content,
            "content_type": content_type,
        }
    except URLError as error:
        raise RuntimeError(f"Network error while reaching upstream API: {error}") from error


def handle_request_file(
    request_file: Path, response_dir: Path, args: argparse.Namespace
) -> None:
    request_data = json.loads(request_file.read_text(encoding="utf-8"))
    request_key = request_data.get("key", request_file.stem)
    LOGGER.info("Processing request %s", request_key)
    result = forward_request(request_data, args)
    payload = {
        "key": request_key,
        "status": result["status"],
        "status_code": result["status_code"],
        "headers": result["headers"],
        "content": result["content"],
        "content_type": result["content_type"],
        "sha256": hashlib.sha256(
            json.dumps(result["content"], ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest(),
        "timestamp": time.time(),
    }
    if request_data.get("path") == "/v1/messages":
        content = result.get("content")
        if isinstance(content, dict):
            stop_reason = content.get("stop_reason")
            model = content.get("model")
            usage = content.get("usage")
            blocks = content.get("content")
            block_types: list[str] = []
            if isinstance(blocks, list):
                for block in blocks[:8]:
                    if isinstance(block, dict):
                        block_types.append(str(block.get("type", "?")))
                    else:
                        block_types.append(type(block).__name__)
            LOGGER.info(
                "Upstream /v1/messages summary: stop_reason=%s model=%s block_types=%s usage=%s",
                stop_reason,
                model,
                block_types,
                usage,
            )
        else:
            LOGGER.info(
                "Upstream /v1/messages returned non-dict content of type %s",
                type(content).__name__,
            )
    atomic_write_json(response_dir / f"{request_key}.json", payload)
    request_file.unlink(missing_ok=True)
    LOGGER.info("Finished request %s with status %s", request_key, result["status_code"])


def cleanup_old_responses(response_dir: Path, response_ttl: float) -> None:
    if response_ttl <= 0:
        return
    now = time.time()
    for response_file in response_dir.glob("*.json"):
        try:
            if now - response_file.stat().st_mtime > response_ttl:
                response_file.unlink()
        except FileNotFoundError:
            continue


def main() -> int:
    args = parse_args()
    shared_base = Path(args.shared_base).expanduser().resolve()
    request_dir = shared_base / "requests"
    response_dir = shared_base / "responses"
    log_dir = shared_base / "logs"
    request_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir, args.verbose)
    LOGGER.info("Watching %s and forwarding to %s", request_dir, args.base_url)

    idle_since = time.monotonic()
    try:
        while True:
            handled_any = False
            request_files = sorted(request_dir.glob("*.json"))
            for request_file in request_files:
                handled_any = True
                try:
                    handle_request_file(request_file, response_dir, args)
                except Exception as error:  # noqa: BLE001
                    LOGGER.exception("Failed to process %s", request_file.name)
                    request_key = request_file.stem
                    try:
                        request_payload = json.loads(
                            request_file.read_text(encoding="utf-8")
                        )
                        request_key = request_payload.get("key", request_key)
                    except Exception:  # noqa: BLE001
                        pass
                    payload = {
                        "key": request_key,
                        "status": "error",
                        "status_code": 502,
                        "error": str(error),
                        "error_type": type(error).__name__,
                        "timestamp": time.time(),
                    }
                    atomic_write_json(response_dir / f"{request_key}.json", payload)
                    request_file.unlink(missing_ok=True)

            cleanup_old_responses(response_dir, args.response_ttl)
            if handled_any:
                idle_since = time.monotonic()

            if args.once:
                return 0

            if not handled_any and args.idle_exit_seconds > 0:
                if time.monotonic() - idle_since >= args.idle_exit_seconds:
                    LOGGER.info("Idle timeout reached, exiting.")
                    return 0

            if not handled_any:
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
