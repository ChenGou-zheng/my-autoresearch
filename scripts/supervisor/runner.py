"""Launch and monitor one opencode session for the autoresearch supervisor."""

from __future__ import annotations

import datetime as dt
import select
import subprocess
import time
from pathlib import Path

from autoresearch_common import (
    build_opencode_command_with_controls,
    format_command,
    load_json,
    terminate_process_group,
    workspace_dir,
)
from supervisor.state import (
    clear_opencode_session,
    now,
    record_opencode_session,
    supervisor_seconds,
)


def launch_session(
    cycle: int,
    dry_run: bool,
    prompt_override: str | None,
    config: dict,
    settings_path: Path,
    session_log_dir: Path,
    supervisor_config: dict,
    state_path: Path,
) -> tuple[int, bool]:
    settings = load_json(settings_path)
    cmd, should_stop_after, events = build_opencode_command_with_controls(
        settings,
        prompt_override,
        consume_controls=not dry_run,
        config=config,
    )
    print(f"[{now()}] launching cycle {cycle}: {format_command(cmd)}")
    if events:
        print(f"[{now()}] applied {len(events)} pending user control event(s)")

    if dry_run:
        return 0, should_stop_after

    session_log_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = session_log_dir / f"session-{stamp}-cycle{cycle}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# started_at: {now()}\n")
        log.write(f"# command: {format_command(cmd)}\n\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=workspace_dir(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        record_opencode_session(state_path, proc.pid, cycle, str(log_path))
        assert proc.stdout is not None
        timed_out = False
        kill_result = None
        timeout_seconds = supervisor_seconds(supervisor_config, "opencode_timeout_seconds")
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
                    supervisor_seconds(supervisor_config, "kill_grace_seconds"),
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
                return_code = proc.wait(timeout=max(1, supervisor_seconds(supervisor_config, "kill_grace_seconds") + 2))
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
        clear_opencode_session(state_path, return_code, timed_out=timed_out, kill_result=kill_result)
        log.write(f"\n# finished_at: {now()}\n")
        log.write(f"# return_code: {return_code}\n")

    print(f"[{now()}] cycle {cycle} exited with {return_code}; log: {log_path}")
    return return_code, should_stop_after
