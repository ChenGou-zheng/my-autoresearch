#!/usr/bin/env python3
"""Keep the autoresearch loop running across opencode sessions.

The agent can start long jobs in the background and then exit. This supervisor
watches `run_state.json`; if a recorded active process is still alive, it waits.
Once no active job is running, it launches the next `opencode run` using
`next_run.json`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import select
import subprocess
import sys
import time
from pathlib import Path

from autoresearch_common import (
    build_opencode_command_with_controls,
    file_path,
    format_command,
    load_config,
    load_json,
    next_run_path,
    process_status,
    runtime_dir,
    terminate_process_group,
    workspace_dir,
    write_json,
)
from autoresearch_control import append_event, pending_events


CONFIG = load_config()
STATE_PATH = file_path("state", CONFIG)
SETTINGS_PATH = next_run_path(CONFIG)
SESSION_LOG_DIR = runtime_dir("sessions", CONFIG)
SUPERVISOR_CONFIG = CONFIG.get("supervisor") or {}


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


def supervisor_seconds(name: str) -> int:
    try:
        return int(SUPERVISOR_CONFIG.get(name, 0))
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


def mark_killed_process(state: dict, pid: int, kind: str, reason: str, kill_result: dict) -> None:
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
    write_json(STATE_PATH, state)


def parse_metric(raw: object) -> float | None:
    try:
        text = str(raw).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def normalized_target(termination: dict) -> float | None:
    target = parse_metric(termination.get("target"))
    if target is None:
        return None
    if str(termination.get("scale") or "unit").lower() == "percent":
        return target / 100.0
    return target


def termination_results_path(termination: dict) -> Path:
    key = str(termination.get("results_file") or "results")
    if key in CONFIG["files"]:
        return file_path(key, CONFIG)
    path = Path(key).expanduser()
    if not path.is_absolute():
        path = CONFIG["state_dir"] / path
    return path.resolve()


def best_result_metric(termination: dict) -> tuple[float | None, dict | None]:
    path = termination_results_path(termination)
    if not path.exists():
        return None, None

    metric_column = str(termination.get("metric_column") or "primary_metric")
    eligible = set(termination.get("eligible_statuses") or ["keep", "continue"])
    best_metric: float | None = None
    best_row: dict | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or metric_column not in reader.fieldnames:
            return None, None
        for row in reader:
            status = str(row.get("status") or "").strip()
            if eligible and status not in eligible:
                continue
            metric = parse_metric(row.get(metric_column))
            if metric is None:
                continue
            if best_metric is None or metric > best_metric:
                best_metric = metric
                best_row = row
    return best_metric, best_row


def queue_target_finish_if_needed(dry_run: bool) -> bool:
    termination = CONFIG.get("termination") or {}
    mode = str(termination.get("mode") or "manual").lower()
    if mode in {"manual", "off", "never"}:
        return False

    target = normalized_target(termination)
    if target is None:
        return False

    state = load_json(STATE_PATH, default={})
    recorded = state.get("termination")
    if isinstance(recorded, dict) and recorded.get("finalization_started"):
        print(f"[{now()}] target finalization already started; stopping supervisor loop")
        return True

    best_metric, best_row = best_result_metric(termination)
    if best_metric is None or best_metric < target:
        return False

    message = (
        f"Target reached: {termination.get('metric_column', 'primary_metric')} "
        f"{best_metric:g} >= {target:g}. Do final synchronization and stop."
    )
    if termination.get("finalize_with_agent") is False:
        print(f"[{now()}] target reached; stopping without final agent session: {message}")
        if not dry_run:
            state["termination"] = {
                "target_reached": True,
                "finalization_started": False,
                "finalization_completed": True,
                "best_result": best_metric,
                "target": target,
                "source": str(termination_results_path(termination)),
                "matched_row": best_row,
                "reason": message,
                "completed_at": now(),
            }
            write_json(STATE_PATH, state)
        return True

    if any(event.get("type") == "finish" and not event.get("consumed_at") for event in pending_events()):
        print(f"[{now()}] target reached; pending finish event already exists")
    elif dry_run:
        print(f"[{now()}] target reached; would queue finish event: {message}")
    else:
        event = append_event("finish", message, force=False)
        print(f"[{now()}] target reached; queued finish event {event['id'][:8]}")

    if not dry_run:
        state["termination"] = {
            "target_reached": True,
            "finalization_started": True,
            "finalization_completed": False,
            "best_result": best_metric,
            "target": target,
            "source": str(termination_results_path(termination)),
            "matched_row": best_row,
            "reason": message,
            "updated_at": now(),
        }
        write_json(STATE_PATH, state)
    return False


def mark_target_finalization_completed() -> None:
    state = load_json(STATE_PATH, default={})
    termination = state.get("termination")
    if not isinstance(termination, dict) or not termination.get("finalization_started"):
        return
    termination["finalization_completed"] = True
    termination["completed_at"] = now()
    state["termination"] = termination
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


def clear_opencode_session(return_code: int, timed_out: bool = False, kill_result: dict | None = None) -> None:
    state = load_json(STATE_PATH, default={})
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

        stale_seconds = supervisor_seconds("active_process_stale_seconds")
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
                    supervisor_seconds("kill_grace_seconds"),
                )
                mark_killed_process(
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
        timed_out = False
        kill_result = None
        timeout_seconds = supervisor_seconds("opencode_timeout_seconds")
        started = time.monotonic()
        while True:
            if proc.poll() is not None:
                remaining = proc.stdout.read()
                if remaining:
                    print(remaining, end="")
                    log.write(remaining)
                break

            if timeout_seconds > 0 and time.monotonic() - started > timeout_seconds:
                print(f"[{now()}] opencode session exceeded {timeout_seconds}s; terminating pid {proc.pid}")
                timed_out = True
                kill_result = terminate_process_group(
                    proc.pid,
                    supervisor_seconds("kill_grace_seconds"),
                )
                break

            readable, _, _ = select.select([proc.stdout], [], [], 1)
            if readable:
                line = proc.stdout.readline()
                if line:
                    print(line, end="")
                    log.write(line)
        if timed_out:
            try:
                return_code = proc.wait(timeout=max(1, supervisor_seconds("kill_grace_seconds") + 2))
            except subprocess.TimeoutExpired:
                proc.kill()
                if kill_result is None:
                    kill_result = {"pid": proc.pid}
                kill_result["sent_kill"] = True
                return_code = proc.wait(timeout=5)
        else:
            return_code = proc.wait()
        if timed_out and kill_result is not None:
            kill_result["terminated"] = True
        clear_opencode_session(return_code, timed_out=timed_out, kill_result=kill_result)
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
        if queue_target_finish_if_needed(args.dry_run):
            return 0
        cycle += 1
        prompt_override = args.prompt_option or args.prompt_arg
        return_code, should_stop_after = launch_session(cycle, args.dry_run, prompt_override)
        if args.dry_run:
            return return_code
        if should_stop_after:
            mark_target_finalization_completed()
            print(f"[{now()}] finish control event consumed; stopping supervisor loop")
            return return_code
        if return_code != 0 and args.stop_on_error:
            return return_code
        time.sleep(5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
