from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]


def _alloc_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _copytree(src: Path, dst: Path) -> None:
    if os.path.lexists(dst):
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    shutil.copytree(src, dst)


class RuntimeSandbox:
    def __init__(self, *, repo_root: Path = REPO_ROOT):
        self.repo_root = repo_root
        base_dir_raw = os.environ.get(
            "OPENRLHF_RUNTIME_BASE_DIR",
            str(repo_root / "rl_memory" / "runs" / "runtime_sandboxes"),
        )
        base_dir = Path(base_dir_raw).resolve()
        sandbox_id = os.environ.get(
            "OPENRLHF_RUNTIME_ID",
            f"pid{os.getpid()}_{int(time.time() * 1000)}_{uuid4().hex[:8]}",
        )
        self.root = base_dir / sandbox_id
        self.port = _alloc_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.server_log_path = self.root / "server.log"
        self._server_proc: subprocess.Popen[str] | None = None
        self._keep = os.environ.get("OPENRLHF_RUNTIME_KEEP", "1") != "0"
        self._prepared = False
        atexit.register(self.close)

    @property
    def state_path(self) -> Path:
        return self.root / "env" / "state.json"

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["WEBAGENT_RUNTIME_ROOT"] = str(self.root)
        env["WEBAGENT_SERVER_PORT"] = str(self.port)
        env["WEBAGENT_SERVER_BASE_URL"] = self.base_url
        return env

    def activate_process_env(self) -> None:
        os.environ["WEBAGENT_RUNTIME_ROOT"] = str(self.root)
        os.environ["WEBAGENT_SERVER_PORT"] = str(self.port)
        os.environ["WEBAGENT_SERVER_BASE_URL"] = self.base_url

    def prepare(self) -> None:
        if self._prepared:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        _copytree(self.repo_root / "env", self.root / "env")
        _copytree(self.repo_root / "tasks", self.root / "tasks")

        sites_link = self.root / "sites"
        if sites_link.exists() or sites_link.is_symlink():
            sites_link.unlink()
        sites_link.symlink_to(self.repo_root / "sites", target_is_directory=True)

        database_link = self.root / "database"
        if database_link.exists() or database_link.is_symlink():
            database_link.unlink()
        database_link.symlink_to(self.repo_root / "database", target_is_directory=True)

        self._prepared = True

    def start_server(self) -> None:
        self.prepare()
        if self._server_proc is not None and self._server_proc.poll() is None:
            return

        self.server_log_path.parent.mkdir(parents=True, exist_ok=True)
        last_error = "server did not start"
        for _ in range(3):
            self.port = _alloc_port()
            self.base_url = f"http://127.0.0.1:{self.port}"
            log_fh = open(self.server_log_path, "a", encoding="utf-8")
            self._server_proc = subprocess.Popen(
                [sys.executable, str(self.repo_root / "server.py"), str(self.port)],
                cwd=str(self.repo_root),
                env=self.env(),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                self._wait_until_ready()
                return
            except RuntimeError as exc:
                last_error = str(exc)
                if self._server_proc is not None and self._server_proc.poll() is None:
                    self._server_proc.terminate()
                    try:
                        self._server_proc.wait(timeout=3)
                    except Exception:
                        self._server_proc.kill()
                self._server_proc = None
                time.sleep(0.2)
        raise RuntimeError(last_error)

    def _log_tail(self, max_lines: int = 40) -> str:
        if not self.server_log_path.exists():
            return "<no server log found>"
        try:
            lines = self.server_log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as exc:  # pragma: no cover - diagnostic path
            return f"<failed to read server log: {exc}>"
        tail = lines[-max_lines:]
        return "\n".join(tail) if tail else "<empty server log>"

    def _wait_until_ready(self) -> None:
        deadline = time.time() + 20
        last_error = "server did not respond"
        while time.time() < deadline:
            if self._server_proc is not None and self._server_proc.poll() is not None:
                raise RuntimeError(
                    f"Sandbox server exited early for {self.root}. Log tail:\n{self._log_tail()}"
                )
            try:
                with urllib.request.urlopen(f"{self.base_url}/api/env", timeout=1) as resp:
                    if 200 <= getattr(resp, "status", 200) < 500:
                        return
            except Exception as exc:  # pragma: no cover - transient startup path
                last_error = str(exc)
                time.sleep(0.2)
        raise RuntimeError(
            f"Timed out waiting for sandbox server at {self.base_url}: {last_error}\nLog tail:\n{self._log_tail()}"
        )

    def close(self) -> None:
        if self._server_proc is not None and self._server_proc.poll() is None:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=5)
            except Exception:
                self._server_proc.kill()
            self._server_proc = None
        if not self._keep and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
