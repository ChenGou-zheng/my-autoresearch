#!/usr/bin/env python3
"""Keep the autoresearch loop running across opencode sessions.

The agent can start long jobs in the background and then exit. This supervisor
watches `run_state.json`; if a recorded active process is still alive, it waits.
Once no active job is running, it launches the next `opencode run` using
`next_run.json`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time

from autoresearch_common import (
    build_opencode_command_with_controls,
    file_path,
    format_command,
    load_config,
    load_json,
    next_run_path,
    process_status,
    workspace_dir,
    HARNESS_DIR,
    write_json,
)


CONFIG = load_config()
STATE_PATH = file_path("state", CONFIG)
SETTINGS_PATH = next_run_path(CONFIG)
SESSION_LOG_DIR = HARNESS_DIR / "autoresearch" / "sessions"


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def describe_pid(pid: int) -> str:
    try:
        output = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "pid=,stat=,etime=,cmd="],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return f"pid {pid}"
    return output or f"pid {pid}"


def get_active_process(state: dict) -> tuple[int | None, str]:
    active_process = state.get("active_process")
    if isinstance(active_process, dict):
        pid = active_process.get("pid")
        kind = str(active_process.get("kind") or "process")
    else:
        pid = None
        kind = "process"

    if not pid and state.get("training_pid"):
        pid = state.get("training_pid")
        kind = "training"

    try:
        return int(pid), kind
    except (TypeError, ValueError):
        return None, kind


def mark_stale_process(state: dict, pid: int, kind: str) -> None:
    detected_at = now()
    state["active"] = False
    state["last_status"] = "stopped"
    state["last_updated"] = detected_at
    state["stale_process"] = {"pid": pid, "kind": kind, "detected_at": detected_at}
    state["active_process"] = None
    if str(state.get("training_pid")) == str(pid):
        state["training_pid"] = None
    write_json(STATE_PATH, state)


def record_opencode_session(pid: int, cycle: int, log_path: str) -> None:
    state = load_json(STATE_PATH, default={})
    state["active"] = True
    state["last_status"] = "running"
    state["last_updated"] = now()
    state["opencode_session"] = {
        "pid": pid,
        "kind": "opencode",
        "cycle": cycle,
        "log_path": log_path,
        "started_at": now(),
    }
    write_json(STATE_PATH, state)


def clear_opencode_session(return_code: int) -> None:
    state = load_json(STATE_PATH, default={})
    session = state.get("opencode_session")
    if isinstance(session, dict):
        session["finished_at"] = now()
        session["return_code"] = return_code
        state["last_opencode_session"] = session
    state["opencode_session"] = None
    if not state.get("active_process") and not state.get("training_pid"):
        state["active"] = False
        if state.get("last_status") == "running":
            state["last_status"] = "stopped"
    state["last_updated"] = now()
    write_json(STATE_PATH, state)


def wait_for_active_process(poll_seconds: int, dry_run: bool) -> bool:
    while True:
        state = load_json(STATE_PATH, default={})
        status = state.get("last_status")
        pid, kind = get_active_process(state)
        if not pid or status != "running":
            return False

        status = process_status(pid)
        if status != "alive":
            if status == "zombie":
                detail = f"is a zombie and cannot make progress: {describe_pid(pid)}"
            else:
                detail = "is no longer running"
            print(f"[{now()}] recorded {kind} pid {pid} {detail}")
            if not dry_run:
                mark_stale_process(state, pid, kind)
            return False

        print(f"[{now()}] waiting for {kind}: {describe_pid(pid)}")
        if dry_run:
            return True
        time.sleep(poll_seconds)


def launch_session(cycle: int, dry_run: bool, prompt_override: str | None) -> tuple[int, bool]:
    settings = load_json(SETTINGS_PATH)
    cmd, should_stop_after, events = build_opencode_command_with_controls(
        settings,
        prompt_override,
        consume_controls=not dry_run,
        config=CONFIG,
    )
    print(f"[{now()}] launching cycle {cycle}: {format_command(cmd)}")
    if events:
        print(f"[{now()}] applied {len(events)} pending user control event(s)")

    if dry_run:
        return 0, should_stop_after

    SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = SESSION_LOG_DIR / f"session-{stamp}-cycle{cycle}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# started_at: {now()}\n")
        log.write(f"# command: {format_command(cmd)}\n\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=workspace_dir(CONFIG),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        record_opencode_session(proc.pid, cycle, str(log_path))
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        return_code = proc.wait()
        clear_opencode_session(return_code)
        log.write(f"\n# finished_at: {now()}\n")
        log.write(f"# return_code: {return_code}\n")

    print(f"[{now()}] cycle {cycle} exited with {return_code}; log: {log_path}")
    return return_code, should_stop_after


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the unattended autoresearch loop.")
    parser.add_argument(
        "prompt_arg",
        nargs="?",
        default=None,
        help="Override the prompt passed to opencode run for launched sessions.",
    )
    parser.add_argument(
        "--prompt",
        dest="prompt_option",
        default=None,
        help="Override the prompt passed to opencode run. Takes precedence over the positional prompt.",
    )
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop if opencode exits non-zero.",
    )
    args = parser.parse_args()

    cycle = 0
    while args.max_cycles == 0 or cycle < args.max_cycles:
        waiting = wait_for_active_process(args.poll_seconds, args.dry_run)
        if args.dry_run and waiting:
            return 0
        cycle += 1
        prompt_override = args.prompt_option or args.prompt_arg
        return_code, should_stop_after = launch_session(cycle, args.dry_run, prompt_override)
        if args.dry_run:
            return return_code
        if should_stop_after:
            print(f"[{now()}] finish control event consumed; stopping supervisor loop")
            return return_code
        if return_code != 0 and args.stop_on_error:
            return return_code
        time.sleep(5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
