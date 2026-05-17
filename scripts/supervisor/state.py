"""State and process helpers for the autoresearch supervisor."""

from __future__ import annotations

import datetime as dt
import subprocess
import time
from pathlib import Path

from autoresearch_common import load_json, process_status, terminate_process_group, write_json


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def parse_time(value: object) -> dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed


def seconds_since(value: object) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return (dt.datetime.now().astimezone() - parsed).total_seconds()


def supervisor_seconds(supervisor_config: dict, name: str) -> int:
    try:
        return int(supervisor_config.get(name, 0))
    except (TypeError, ValueError):
        return 0


def describe_pid(pid: int) -> str:
    try:
        output = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "pid=,stat=,etime=,cmd="],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
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


def mark_stale_process(state_path: Path, state: dict, pid: int, kind: str) -> None:
    detected_at = now()
    state["active"] = False
    state["last_status"] = "stopped"
    state["last_updated"] = detected_at
    state["stale_process"] = {"pid": pid, "kind": kind, "detected_at": detected_at}
    state["active_process"] = None
    if str(state.get("training_pid")) == str(pid):
        state["training_pid"] = None
    write_json(state_path, state)


def mark_killed_process(
    state_path: Path,
    state: dict,
    pid: int,
    kind: str,
    reason: str,
    kill_result: dict,
) -> None:
    detected_at = now()
    state["active"] = False
    state["last_status"] = "timed_out"
    state["last_updated"] = detected_at
    state["killed_process"] = {
        "pid": pid,
        "kind": kind,
        "reason": reason,
        "detected_at": detected_at,
        "kill_result": kill_result,
    }
    state["active_process"] = None
    if str(state.get("training_pid")) == str(pid):
        state["training_pid"] = None
    write_json(state_path, state)


def record_opencode_session(state_path: Path, pid: int, cycle: int, log_path: str) -> None:
    state = load_json(state_path, default={})
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
    write_json(state_path, state)


def clear_opencode_session(
    state_path: Path,
    return_code: int,
    timed_out: bool = False,
    kill_result: dict | None = None,
) -> None:
    state = load_json(state_path, default={})
    session = state.get("opencode_session")
    if isinstance(session, dict):
        session["finished_at"] = now()
        session["return_code"] = return_code
        if timed_out:
            session["timed_out"] = True
            session["kill_result"] = kill_result or {}
        state["last_opencode_session"] = session
        if timed_out:
            state["timed_out_opencode_session"] = session
    state["opencode_session"] = None
    if not state.get("active_process") and not state.get("training_pid"):
        state["active"] = False
        if timed_out:
            state["last_status"] = "timed_out"
        elif state.get("last_status") == "running":
            state["last_status"] = "stopped"
    state["last_updated"] = now()
    write_json(state_path, state)


def wait_for_active_process(
    state_path: Path,
    supervisor_config: dict,
    poll_seconds: int,
    dry_run: bool,
) -> bool:
    while True:
        state = load_json(state_path, default={})
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
                mark_stale_process(state_path, state, pid, kind)
            return False

        stale_seconds = supervisor_seconds(supervisor_config, "active_process_stale_seconds")
        last_progress = None
        active_process = state.get("active_process")
        if isinstance(active_process, dict):
            last_progress = active_process.get("last_updated") or active_process.get("started_at")
        last_progress = last_progress or state.get("last_updated")
        age = seconds_since(last_progress)
        if stale_seconds > 0 and age is not None and age > stale_seconds:
            print(
                f"[{now()}] recorded {kind} pid {pid} has no state progress "
                f"for {int(age)}s; terminating: {describe_pid(pid)}"
            )
            if not dry_run:
                kill_result = terminate_process_group(
                    pid,
                    supervisor_seconds(supervisor_config, "kill_grace_seconds"),
                )
                mark_killed_process(
                    state_path,
                    state,
                    pid,
                    kind,
                    f"no state progress for {int(age)}s",
                    kill_result,
                )
            return False

        print(f"[{now()}] waiting for {kind}: {describe_pid(pid)}")
        if dry_run:
            return True
        time.sleep(poll_seconds)
