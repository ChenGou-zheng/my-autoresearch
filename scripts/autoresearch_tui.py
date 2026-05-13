#!/usr/bin/env python3
"""Minimal read-only TUI for observing an autoresearch run."""

from __future__ import annotations

import curses
import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Iterable

from autoresearch_common import PROJECT_DIR


REFRESH_SECONDS = 1.0
STATE_PATH = PROJECT_DIR / "run_state.json"
TODO_PATH = PROJECT_DIR / "todo.md"
RESULTS_PATH = PROJECT_DIR / "results.tsv"
SESSION_DIR = PROJECT_DIR / "autoresearch" / "sessions"
LOG_DIR = PROJECT_DIR / "autoresearch" / "logs"


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def load_json(path: Path) -> dict:
    try:
        return json.loads(read_text(path, "{}"))
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


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_results(limit: int = 8) -> tuple[list[str], list[list[str]]]:
    rows = [line.split("\t") for line in read_text(RESULTS_PATH).splitlines() if line.strip()]
    if not rows:
        return [], []
    header, body = rows[0], rows[1:]
    return header, body[-limit:]


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


def clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: max(0, width - 3)] + "..."


def safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = win.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    try:
        win.addstr(y, x, clip(text, max(0, width - x - 1)), attr)
    except curses.error:
        pass


def draw_box(win: curses.window, title: str) -> None:
    win.erase()
    win.box()
    safe_addstr(win, 0, 2, f" {title} ", curses.A_BOLD)


def draw_status(win: curses.window, state: dict, latest_log: Path | None) -> None:
    draw_box(win, "Status")
    active_process = state.get("active_process")
    pid = None
    if isinstance(active_process, dict):
        pid = active_process.get("pid")
    if not pid:
        pid = state.get("training_pid")
    try:
        pid_value = int(pid) if pid else None
    except (TypeError, ValueError):
        pid_value = None

    status = str(state.get("last_status") or "unknown")
    live = pid_alive(pid_value)
    current = "running" if live else status
    best_fid = state.get("best_official_fid", "na")
    best_proxy = state.get("best_proxy_fid50k", "na")
    branch = state.get("current_branch", "na")
    checkpoint = state.get("best_checkpoint", "na")

    safe_addstr(win, 1, 2, f"state: {current}    pid: {pid_value or 'none'}    branch: {branch}")
    safe_addstr(win, 2, 2, f"best official FID: {best_fid}    proxy: {best_proxy}")
    safe_addstr(win, 3, 2, f"best checkpoint: {checkpoint}")
    if latest_log:
        rel = latest_log.relative_to(PROJECT_DIR)
        safe_addstr(win, 4, 2, f"latest log: {rel} ({format_age(latest_log)})")
    else:
        safe_addstr(win, 4, 2, "latest log: none")


def draw_todo(win: curses.window) -> None:
    draw_box(win, "Todo")
    for idx, line in enumerate(parse_todo(limit=max(1, win.getmaxyx()[0] - 2)), start=1):
        attr = curses.A_BOLD if line.startswith("## ") else 0
        safe_addstr(win, idx, 2, line, attr)


def draw_results(win: curses.window) -> None:
    draw_box(win, "Results")
    height, width = win.getmaxyx()
    header, rows = parse_results(limit=max(1, height - 3))
    if not header:
        safe_addstr(win, 1, 2, "No results.tsv rows yet.")
        return

    columns = ["commit", "official_fid", "proxy_fid50k", "status", "description"]
    indexes = [header.index(col) for col in columns if col in header]
    selected = [header[index] for index in indexes]
    safe_addstr(win, 1, 2, " | ".join(selected), curses.A_BOLD)
    for y, row in enumerate(rows, start=2):
        cells = [row[index] if index < len(row) else "" for index in indexes]
        line = " | ".join(cells)
        safe_addstr(win, y, 2, line[: max(0, width - 4)])


def draw_log(win: curses.window, latest_log: Path | None) -> None:
    title = "Latest Log"
    if latest_log:
        title = f"Latest Log: {latest_log.name}"
    draw_box(win, title)
    if latest_log is None:
        safe_addstr(win, 1, 2, "No log files found.")
        return
    max_lines = max(1, win.getmaxyx()[0] - 2)
    for idx, line in enumerate(tail_lines(latest_log, max_lines), start=1):
        safe_addstr(win, idx, 2, line)


def render(screen: curses.window) -> None:
    curses.curs_set(0)
    screen.nodelay(True)
    screen.timeout(100)

    while True:
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key == curses.KEY_RESIZE:
            screen.erase()

        state = load_json(STATE_PATH)
        latest = newest_log()
        height, width = screen.getmaxyx()
        screen.erase()

        if height < 20 or width < 70:
            safe_addstr(screen, 0, 0, "Terminal too small. Need at least 70x20. Press q to quit.")
            screen.refresh()
            time.sleep(REFRESH_SECONDS)
            continue

        status_height = 7
        footer_height = 1
        middle_height = max(6, (height - status_height - footer_height) // 2)
        log_height = height - status_height - middle_height - footer_height
        left_width = max(30, width // 3)
        right_width = width - left_width

        status_win = curses.newwin(status_height, width, 0, 0)
        todo_win = curses.newwin(middle_height, left_width, status_height, 0)
        results_win = curses.newwin(middle_height, right_width, status_height, left_width)
        log_win = curses.newwin(log_height, width, status_height + middle_height, 0)

        draw_status(status_win, state, latest)
        draw_todo(todo_win)
        draw_results(results_win)
        draw_log(log_win, latest)

        for win in (status_win, todo_win, results_win, log_win):
            win.noutrefresh()

        now = dt.datetime.now().strftime("%H:%M:%S")
        safe_addstr(screen, height - 1, 0, f"q quit | auto-refresh {REFRESH_SECONDS:.0f}s | {now}")
        curses.doupdate()
        time.sleep(REFRESH_SECONDS)


def main() -> int:
    try:
        curses.wrapper(render)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
