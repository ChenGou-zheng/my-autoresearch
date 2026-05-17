#!/usr/bin/env python3
"""Keep the autoresearch loop running across opencode sessions."""

from __future__ import annotations

import argparse
import sys
import time

from autoresearch_common import file_path, load_config, next_run_path, runtime_dir
from supervisor.runner import launch_session
from supervisor.state import now, wait_for_active_process
from supervisor.termination import (
    mark_target_finalization_completed,
    queue_target_finish_if_needed,
)


CONFIG = load_config()
STATE_PATH = file_path("state", CONFIG)
SETTINGS_PATH = next_run_path(CONFIG)
SESSION_LOG_DIR = runtime_dir("sessions", CONFIG)
SUPERVISOR_CONFIG = CONFIG.get("supervisor") or {}


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
        waiting = wait_for_active_process(
            STATE_PATH,
            SUPERVISOR_CONFIG,
            args.poll_seconds,
            args.dry_run,
        )
        if args.dry_run and waiting:
            return 0
        if queue_target_finish_if_needed(CONFIG, STATE_PATH, args.dry_run):
            return 0
        cycle += 1
        prompt_override = args.prompt_option or args.prompt_arg
        return_code, should_stop_after = launch_session(
            cycle,
            args.dry_run,
            prompt_override,
            CONFIG,
            SETTINGS_PATH,
            SESSION_LOG_DIR,
            SUPERVISOR_CONFIG,
            STATE_PATH,
        )
        if args.dry_run:
            return return_code
        if should_stop_after:
            mark_target_finalization_completed(STATE_PATH, return_code)
            print(f"[{now()}] finish control event consumed; stopping supervisor loop")
            return return_code
        if return_code != 0 and args.stop_on_error:
            return return_code
        time.sleep(5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
