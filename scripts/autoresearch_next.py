#!/usr/bin/env python3
"""Launch the next autoresearch session from next_run.json."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from autoresearch_common import (
    build_opencode_command_with_controls,
    format_command,
    load_json,
    load_config,
    next_run_path,
    workspace_dir,
)


def load_settings(path: Path) -> dict:
    try:
        return load_json(path)
    except SystemExit as exc:
        message = str(exc)
        if message.startswith("missing required file:"):
            raise SystemExit(f"settings file not found: {path}") from None
        raise


def build_command(
    settings: dict,
    prompt_override: str | None,
    consume_controls: bool = True,
    config: dict | None = None,
) -> list[str]:
    cmd, _should_stop_after, _events = build_opencode_command_with_controls(
        settings,
        prompt_override,
        consume_controls=consume_controls,
        config=config,
    )
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the next opencode autoresearch session."
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=None,
        help="Path to next_run.json",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override the prompt from next_run.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the opencode command without running it",
    )
    args = parser.parse_args()

    config = load_config()
    settings_path = args.settings or next_run_path(config)
    settings = load_settings(settings_path)
    cmd = build_command(settings, args.prompt, consume_controls=not args.dry_run, config=config)

    print(format_command(cmd))
    if args.dry_run:
        return 0

    return subprocess.run(cmd, cwd=workspace_dir(config)).returncode


if __name__ == "__main__":
    sys.exit(main())
