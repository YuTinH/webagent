#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one Anthropic-compatible task through a shared-disk relay.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--shared-base",
        required=True,
        help="Shared directory visible to both GPU and CPU partitions.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Upstream model name.",
    )
    parser.add_argument(
        "--task",
        default="",
        help="Task text. If omitted, --task-file or stdin will be used.",
    )
    parser.add_argument(
        "--task-file",
        default="",
        help="Read task text from this file.",
    )
    parser.add_argument(
        "--system",
        default="",
        help="Optional system prompt.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AGENT_API_KEY", ""),
        help="API key. If omitted here, the CPU relay can inject one with --default-api-key.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=("x-api-key", "bearer", "none"),
        default="x-api-key",
        help="How the API key should be sent.",
    )
    parser.add_argument(
        "--api-path",
        default="/v1/messages",
        help="Upstream API path handled by the CPU relay.",
    )
    parser.add_argument(
        "--anthropic-version",
        default="2023-06-01",
        help="Anthropic API version header.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Max tokens for the generated answer.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="How long to wait for the CPU relay response.",
    )
    parser.add_argument(
        "--extra-body-json",
        default="",
        help="Extra JSON object merged into the request body.",
    )
    parser.add_argument(
        "--save-response",
        default="",
        help="Optional path to save the full response JSON.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full response payload instead of extracting plain text.",
    )
    return parser.parse_args()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp_path.replace(path)


def read_task(args: argparse.Namespace) -> str:
    if args.task:
        return args.task
    if args.task_file:
        return Path(args.task_file).expanduser().read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise SystemExit("Task text is required. Use --task, --task-file, or stdin.")


def build_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }
    if args.anthropic_version:
        headers["anthropic-version"] = args.anthropic_version
    if args.api_key:
        if args.auth_mode == "x-api-key":
            headers["x-api-key"] = args.api_key
        elif args.auth_mode == "bearer":
            headers["authorization"] = f"Bearer {args.api_key}"
    return headers


def build_request_body(args: argparse.Namespace, task: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "messages": [{"role": "user", "content": task}],
    }
    if args.system:
        body["system"] = args.system
    if args.temperature is not None:
        body["temperature"] = args.temperature
    if args.extra_body_json:
        extra_payload = json.loads(args.extra_body_json)
        if not isinstance(extra_payload, dict):
            raise SystemExit("--extra-body-json must be a JSON object.")
        body.update(extra_payload)
    return body


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if isinstance(content.get("output_text"), str):
            return content["output_text"]
        blocks = content.get("content")
        if isinstance(blocks, list):
            pieces: list[str] = []
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    pieces.append(str(block.get("text", "")))
            if pieces:
                return "\n".join(piece for piece in pieces if piece)
        choices = content.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0]
            if isinstance(choice, dict):
                message = choice.get("message")
                if isinstance(message, dict):
                    message_content = message.get("content")
                    if isinstance(message_content, str):
                        return message_content
                    if isinstance(message_content, list):
                        pieces = []
                        for block in message_content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                pieces.append(str(block.get("text", "")))
                        if pieces:
                            return "\n".join(piece for piece in pieces if piece)
        error = content.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    return json.dumps(content, ensure_ascii=False, indent=2)


def wait_for_response(response_file: Path, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if response_file.exists():
            payload = json.loads(response_file.read_text(encoding="utf-8"))
            response_file.unlink(missing_ok=True)
            return payload
        time.sleep(0.05)
    raise TimeoutError(f"Timed out while waiting for {response_file.name}")


def main() -> int:
    args = parse_args()
    task = read_task(args)
    shared_base = Path(args.shared_base).expanduser().resolve()
    request_dir = shared_base / "requests"
    response_dir = shared_base / "responses"
    request_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)

    request_key = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    request_payload = {
        "key": request_key,
        "method": "POST",
        "path": args.api_path,
        "headers": build_headers(args),
        "query_params": {},
        "body": build_request_body(args, task),
        "timestamp": time.time(),
    }

    atomic_write_json(request_dir / f"{request_key}.json", request_payload)
    response_file = response_dir / f"{request_key}.json"

    try:
        response_payload = wait_for_response(response_file, args.timeout_seconds)
    except Exception as error:  # noqa: BLE001
        raise SystemExit(str(error)) from error

    if args.save_response:
        save_path = Path(args.save_response).expanduser()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(save_path, response_payload)

    if response_payload.get("status") == "error":
        message = response_payload.get("error", "Unknown relay error")
        raise SystemExit(f"Relay error: {message}")

    if args.raw:
        print(json.dumps(response_payload, ensure_ascii=False, indent=2))
        return 0

    text = extract_text(response_payload.get("content"))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
