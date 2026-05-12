#!/usr/bin/env python3
"""Keep the autoresearch loop running across opencode sessions.

The agent can start long jobs in the background and then exit. This supervisor
watches `run_state.json`; if a recorded active process is still alive, it waits.
Once no active job is running, it launches the next `opencode run` using
`autoresearch_setting.json`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = PROJECT_DIR / "run_state.json"
SETTINGS_PATH = PROJECT_DIR / "autoresearch_setting.json"
SESSION_LOG_DIR = PROJECT_DIR / "autoresearch" / "sessions"

MODEL_ALIASES = {
    "deepseekv4pro": "deepseek/deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseekv4flash": "deepseek/deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-flash": "deepseek/deepseek-v4-flash",
}

ALLOWED_VARIANTS = {"medium", "high", "xhigh", "max"}
DEFAULT_PROMPT = (
    "Read program.md first. Then read project.md, run_state.json, handoff.md, "
    "todo.md, plan.md, and results.tsv. Summarize current best result, active "
    "or blocked state, and next concrete action before editing or running long "
    "commands. Continue exactly one autoresearch loop iteration unless blocked."
)


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        if default is not None:
            return default
        raise SystemExit(f"missing required file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def describe_pid(pid: int) -> str:
    try:
        output = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "pid=,stat=,etime=,cmd="],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return f"pid {pid}"
    return output or f"pid {pid}"


def resolve_model(raw_model: str) -> str:
    model = raw_model.strip()
    return MODEL_ALIASES.get(model, model)


def resolve_variant(raw_variant: str) -> str:
    variant = raw_variant.strip()
    if variant not in ALLOWED_VARIANTS:
        allowed = ", ".join(sorted(ALLOWED_VARIANTS))
        raise SystemExit(f"unsupported variant {variant!r}; expected one of: {allowed}")
    return variant


def build_opencode_command(settings: dict, prompt_override: str | None = None) -> list[str]:
    raw_model = settings.get("next_model")
    raw_variant = settings.get("next_reasoning_effort")
    if not raw_model:
        raise SystemExit("autoresearch_setting.json is missing next_model")
    if not raw_variant:
        raise SystemExit("autoresearch_setting.json is missing next_reasoning_effort")

    model = resolve_model(str(raw_model))
    variant = resolve_variant(str(raw_variant))
    prompt = prompt_override or str(settings.get("prompt") or DEFAULT_PROMPT)
    return ["opencode", "run", "-m", model, "--variant", variant, prompt]


def format_command(cmd: list[str]) -> str:
    return shlex.join(cmd)


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


def wait_for_active_process(poll_seconds: int, dry_run: bool) -> bool:
    while True:
        state = load_json(STATE_PATH, default={})
        status = state.get("last_status")
        pid, kind = get_active_process(state)
        if not pid or status != "running":
            return False

        if not pid_alive(pid):
            print(f"[{now()}] recorded {kind} pid {pid} is no longer running")
            return False

        print(f"[{now()}] waiting for {kind}: {describe_pid(pid)}")
        if dry_run:
            return True
        time.sleep(poll_seconds)


def launch_session(cycle: int, dry_run: bool, prompt_override: str | None) -> int:
    settings = load_json(SETTINGS_PATH)
    cmd = build_opencode_command(settings, prompt_override)
    print(f"[{now()}] launching cycle {cycle}: {format_command(cmd)}")

    if dry_run:
        return 0

    SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = SESSION_LOG_DIR / f"session-{stamp}-cycle{cycle}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# started_at: {now()}\n")
        log.write(f"# command: {format_command(cmd)}\n\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        return_code = proc.wait()
        log.write(f"\n# finished_at: {now()}\n")
        log.write(f"# return_code: {return_code}\n")

    print(f"[{now()}] cycle {cycle} exited with {return_code}; log: {log_path}")
    return return_code


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
        return_code = launch_session(cycle, args.dry_run, prompt_override)
        if args.dry_run:
            return return_code
        if return_code != 0 and args.stop_on_error:
            return return_code
        time.sleep(5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
