"""Curses application loop for the autoresearch TUI."""

from __future__ import annotations

import curses
import datetime as dt
import time

from tui.render import draw_log, draw_results, draw_status, draw_todo, safe_addstr
from tui.snapshot import build_snapshot


REFRESH_SECONDS = 1.0


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

        snapshot = build_snapshot(
            todo_limit=max(1, middle_height - 2),
            results_limit=max(1, middle_height - 3),
            log_limit=max(1, log_height - 2),
        )

        status_win = curses.newwin(status_height, width, 0, 0)
        todo_win = curses.newwin(middle_height, left_width, status_height, 0)
        results_win = curses.newwin(middle_height, right_width, status_height, left_width)
        log_win = curses.newwin(log_height, width, status_height + middle_height, 0)

        draw_status(status_win, snapshot)
        draw_todo(todo_win, snapshot)
        draw_results(results_win, snapshot)
        draw_log(log_win, snapshot)

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
