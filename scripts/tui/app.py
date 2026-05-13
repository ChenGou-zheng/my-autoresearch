"""Curses application loop for the autoresearch TUI."""

from __future__ import annotations

import curses
import datetime as dt
import time
from dataclasses import dataclass

from autoresearch_common import DEFAULT_STATE
from autoresearch_control import append_event, interrupt_from_state
from tui.render import draw_log, draw_results, draw_status, draw_todo, safe_addstr
from tui.snapshot import build_snapshot


REFRESH_SECONDS = 1.0


@dataclass
class Layout:
    height: int
    width: int
    status_height: int
    middle_height: int
    log_height: int
    left_width: int
    status_win: curses.window
    todo_win: curses.window
    results_win: curses.window
    log_win: curses.window


def read_message(screen: curses.window, event_type: str, force: bool) -> str | None:
    screen.nodelay(False)
    screen.timeout(-1)
    try:
        curses.curs_set(1)
    except curses.error:
        pass

    height, width = screen.getmaxyx()
    prompt = f"{event_type}{' force' if force else ''} message: "
    max_message_width = max(0, width - len(prompt) - 1)
    chars: list[str] = []
    try:
        while True:
            screen.move(height - 1, 0)
            screen.clrtoeol()
            safe_addstr(screen, height - 1, 0, prompt, curses.A_BOLD)
            visible = "".join(chars)[-max_message_width:] if max_message_width else ""
            safe_addstr(screen, height - 1, len(prompt), visible)
            screen.move(height - 1, min(width - 1, len(prompt) + len(visible)))
            screen.refresh()

            key = screen.get_wch()
            if key == "\x1b":
                return None
            if key in ("\n", "\r"):
                return "".join(chars).strip()
            if key in ("\b", "\x7f") or key == curses.KEY_BACKSPACE:
                if chars:
                    chars.pop()
                continue
            if key == "\x15":
                chars.clear()
                continue
            if isinstance(key, str) and key.isprintable():
                chars.append(key)
    except (KeyboardInterrupt, curses.error):
        return None
    finally:
        screen.nodelay(True)
        screen.timeout(100)
        try:
            curses.curs_set(0)
        except curses.error:
            pass


def handle_control_input(screen: curses.window, key: int) -> str:
    mapping = {
        ord("s"): ("suggest", False),
        ord("S"): ("suggest", True),
        ord("f"): ("finish", False),
        ord("F"): ("finish", True),
    }
    event_type, force = mapping[key]
    message = read_message(screen, event_type, force)
    if message is None:
        return "input cancelled"

    event = append_event(event_type, message, force=force)
    if not force:
        return f"queued {event_type} event {event['id'][:8]}"

    killed = interrupt_from_state(DEFAULT_STATE)
    if killed:
        return f"queued force {event_type}; sent TERM to pid(s): {', '.join(map(str, killed))}"
    return f"queued force {event_type}; no live pid found"


def create_layout(height: int, width: int) -> Layout:
    status_height = 7
    footer_height = 1
    middle_height = max(6, (height - status_height - footer_height) // 2)
    log_height = height - status_height - middle_height - footer_height
    left_width = max(30, width // 3)
    right_width = width - left_width

    return Layout(
        height=height,
        width=width,
        status_height=status_height,
        middle_height=middle_height,
        log_height=log_height,
        left_width=left_width,
        status_win=curses.newwin(status_height, width, 0, 0),
        todo_win=curses.newwin(middle_height, left_width, status_height, 0),
        results_win=curses.newwin(middle_height, right_width, status_height, left_width),
        log_win=curses.newwin(log_height, width, status_height + middle_height, 0),
    )


def render(screen: curses.window) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    screen.nodelay(True)
    screen.timeout(100)
    screen.leaveok(True)
    layout: Layout | None = None
    terminal_was_too_small = False
    status_message = ""

    while True:
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("s"), ord("S"), ord("f"), ord("F")):
            status_message = handle_control_input(screen, key)
        resized = False
        if key == curses.KEY_RESIZE:
            screen.erase()
            layout = None
            resized = True

        height, width = screen.getmaxyx()

        if height < 20 or width < 70:
            if resized or not terminal_was_too_small:
                screen.erase()
            safe_addstr(screen, 0, 0, "Terminal too small. Need at least 70x20. Press q to quit.")
            screen.noutrefresh()
            curses.doupdate()
            terminal_was_too_small = True
            time.sleep(REFRESH_SECONDS)
            continue

        if terminal_was_too_small:
            screen.erase()
            layout = None
            terminal_was_too_small = False

        if layout is None or layout.height != height or layout.width != width:
            screen.erase()
            layout = create_layout(height, width)

        snapshot = build_snapshot(
            todo_limit=max(1, layout.middle_height - 2),
            results_limit=max(1, layout.middle_height - 3),
            log_limit=max(1, layout.log_height - 2),
        )

        draw_status(layout.status_win, snapshot)
        draw_todo(layout.todo_win, snapshot)
        draw_results(layout.results_win, snapshot)
        draw_log(layout.log_win, snapshot)

        for win in (layout.status_win, layout.todo_win, layout.results_win, layout.log_win):
            win.noutrefresh()

        now = dt.datetime.now().strftime("%H:%M:%S")
        screen.move(height - 1, 0)
        screen.clrtoeol()
        help_text = "s suggest | S force suggest | f finish | F force finish | q quit"
        footer = f"{help_text} | {now}"
        if status_message:
            footer = f"{status_message} | {footer}"
        safe_addstr(screen, height - 1, 0, footer)
        screen.noutrefresh()
        curses.doupdate()
        time.sleep(REFRESH_SECONDS)


def main() -> int:
    try:
        curses.wrapper(render)
    except KeyboardInterrupt:
        return 130
    return 0
