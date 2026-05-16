"""Read project state files and build a compact TUI snapshot."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from autoresearch_common import file_path, load_config, pid_alive, runtime_dir
from autoresearch_control import pending_events


CONFIG = load_config()
STATE_PATH = file_path("state", CONFIG)
TODO_PATH = file_path("todo", CONFIG)
RESULTS_PATH = file_path("results", CONFIG)
SESSION_DIR = runtime_dir("sessions", CONFIG)
LOG_DIR = runtime_dir("logs", CONFIG)


@dataclass(frozen=True)
class ResultTable:
    header: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class TuiSnapshot:
    state: dict
    status: str
    pid: int | None
    pid_is_alive: bool
    latest_log: Path | None
    latest_log_age: str
    latest_log_lines: list[str]
    todo_lines: list[str]
    results: ResultTable
    pending_control_count: int


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def load_state() -> dict:
    try:
        return json.loads(read_text(STATE_PATH, "{}"))
    except json.JSONDecodeError:
        return {}


def tail_lines(path: Path, limit: int) -> list[str]:
    lines = read_text(path).splitlines()
    return lines[-limit:]


def newest_file(paths: Iterable[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def newest_log() -> Path | None:
    candidates = list(SESSION_DIR.glob("*.log")) + list(LOG_DIR.rglob("*.log"))
    return newest_file(candidates)


def active_pid(state: dict) -> int | None:
    opencode_session = state.get("opencode_session")
    if isinstance(opencode_session, dict):
        pid = _as_pid(opencode_session.get("pid"))
        if pid:
            return pid

    active_process = state.get("active_process")
    pid = None
    if isinstance(active_process, dict):
        pid = active_process.get("pid")
    if not pid:
        pid = state.get("training_pid")
    return _as_pid(pid)


def _as_pid(raw: object) -> int | None:
    try:
        pid = int(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return pid if pid and pid > 0 else None


def parse_results(limit: int = 8) -> ResultTable:
    rows = [line.split("\t") for line in read_text(RESULTS_PATH).splitlines() if line.strip()]
    if not rows:
        return ResultTable(header=[], rows=[])
    header, body = rows[0], rows[1:]
    return ResultTable(header=header, rows=body[-limit:])


def parse_todo(limit: int = 8) -> list[str]:
    visible: list[str] = []
    include_continuation = False
    for line in read_text(TODO_PATH).splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            visible.append(stripped)
            include_continuation = False
        elif stripped.startswith("- ["):
            visible.append(stripped)
            include_continuation = True
        elif include_continuation and stripped:
            visible.append(f"  {stripped}")
        if len(visible) >= limit:
            break
    return visible


def format_age(path: Path | None) -> str:
    if path is None:
        return "none"
    age_seconds = max(0, time.time() - path.stat().st_mtime)
    if age_seconds < 60:
        return f"{int(age_seconds)}s ago"
    if age_seconds < 3600:
        return f"{int(age_seconds // 60)}m ago"
    return f"{int(age_seconds // 3600)}h ago"


def build_snapshot(todo_limit: int = 8, results_limit: int = 8, log_limit: int = 12) -> TuiSnapshot:
    state = load_state()
    pid = active_pid(state)
    live = pid_alive(pid)
    latest = newest_log()
    status = "running" if live else str(state.get("last_status") or "unknown")
    log_lines = tail_lines(latest, log_limit) if latest else []
    return TuiSnapshot(
        state=state,
        status=status,
        pid=pid,
        pid_is_alive=live,
        latest_log=latest,
        latest_log_age=format_age(latest),
        latest_log_lines=log_lines,
        todo_lines=parse_todo(todo_limit),
        results=parse_results(results_limit),
        pending_control_count=len(pending_events()),
    )
