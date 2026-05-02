from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent


def runtime_root() -> Path:
    raw = os.environ.get("WEBAGENT_RUNTIME_ROOT")
    if raw:
        return Path(raw).resolve()
    return REPO_ROOT


def env_dir() -> Path:
    return runtime_root() / "env"


def state_path() -> Path:
    return env_dir() / "state.json"


def db_path() -> Path:
    return runtime_root() / "data.db"


def sites_dir() -> Path:
    return runtime_root() / "sites"


def tasks_dir() -> Path:
    return runtime_root() / "tasks"


def database_dir() -> Path:
    return runtime_root() / "database"


def server_port() -> int:
    raw = os.environ.get("WEBAGENT_SERVER_PORT", "8014").strip()
    try:
        return int(raw)
    except Exception:
        return 8014


def server_base_url() -> str:
    return os.environ.get("WEBAGENT_SERVER_BASE_URL", f"http://localhost:{server_port()}").rstrip("/")

