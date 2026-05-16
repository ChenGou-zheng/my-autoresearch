"""Curses rendering helpers for the autoresearch TUI."""

from __future__ import annotations

import curses

from autoresearch_common import load_config
from tui.snapshot import TuiSnapshot

CONFIG = load_config()


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


def draw_status(win: curses.window, snapshot: TuiSnapshot) -> None:
    draw_box(win, "Status")
    state = snapshot.state
    branch = state.get("current_branch", "na")
    best_metric = state.get("best_primary_metric", "na")
    best_artifact = state.get("best_artifact", "na")

    safe_addstr(
        win,
        1,
        2,
        f"state: {snapshot.status}    pid: {snapshot.pid or 'none'}    branch: {branch}",
    )
    safe_addstr(win, 2, 2, f"best primary metric: {best_metric}")
    safe_addstr(win, 3, 2, f"best artifact: {best_artifact}")
    if snapshot.latest_log:
        try:
            rel = snapshot.latest_log.relative_to(CONFIG["output_dir"])
        except ValueError:
            rel = snapshot.latest_log
        safe_addstr(win, 4, 2, f"latest log: {rel} ({snapshot.latest_log_age})")
    else:
        safe_addstr(win, 4, 2, "latest log: none")
    safe_addstr(win, 5, 2, f"pending user events: {snapshot.pending_control_count}")


def draw_todo(win: curses.window, snapshot: TuiSnapshot) -> None:
    draw_box(win, "Todo")
    for idx, line in enumerate(snapshot.todo_lines, start=1):
        attr = curses.A_BOLD if line.startswith("## ") else 0
        safe_addstr(win, idx, 2, line, attr)


def draw_results(win: curses.window, snapshot: TuiSnapshot) -> None:
    draw_box(win, "Results")
    height, width = win.getmaxyx()
    table = snapshot.results
    if not table.header:
        safe_addstr(win, 1, 2, "No results.tsv rows yet.")
        return

    columns = ["commit", "primary_metric", "secondary_metric", "status", "description"]
    indexes = [table.header.index(col) for col in columns if col in table.header]
    selected = [table.header[index] for index in indexes]
    safe_addstr(win, 1, 2, " | ".join(selected), curses.A_BOLD)
    for y, row in enumerate(table.rows[: max(0, height - 3)], start=2):
        cells = [row[index] if index < len(row) else "" for index in indexes]
        safe_addstr(win, y, 2, " | ".join(cells)[: max(0, width - 4)])


def draw_log(win: curses.window, snapshot: TuiSnapshot) -> None:
    title = "Latest Log"
    if snapshot.latest_log:
        title = f"Latest Log: {snapshot.latest_log.name}"
    draw_box(win, title)
    if snapshot.latest_log is None:
        safe_addstr(win, 1, 2, "No log files found.")
        return
    for idx, line in enumerate(snapshot.latest_log_lines, start=1):
        safe_addstr(win, idx, 2, line)
