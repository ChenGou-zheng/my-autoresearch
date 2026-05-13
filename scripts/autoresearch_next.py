#!/usr/bin/env python3
"""Launch the next autoresearch session from autoresearch_setting.json."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from autoresearch_common import (
    DEFAULT_SETTINGS,
    PROJECT_DIR,
    build_opencode_command_with_controls,
    format_command,
    load_json,
)


def load_settings(path: Path) -> dict:
    try:
        return load_json(path)
    except SystemExit as exc:
        message = str(exc)
        if message.startswith("missing required file:"):
            raise SystemExit(f"settings file not found: {path}") from None
        raise


def build_command(settings: dict, prompt_override: str | None, consume_controls: bool = True) -> list[str]:
    cmd, _should_stop_after, _events = build_opencode_command_with_controls(
        settings,
        prompt_override,
        consume_controls=consume_controls,
    )
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the next opencode autoresearch session."
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS,
        help="Path to autoresearch_setting.json",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Override the prompt from autoresearch_setting.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the opencode command without running it",
    )
    args = parser.parse_args()

    settings = load_settings(args.settings)
    cmd = build_command(settings, args.prompt, consume_controls=not args.dry_run)

    print(format_command(cmd))
    if args.dry_run:
        return 0

    return subprocess.run(cmd, cwd=PROJECT_DIR).returncode


if __name__ == "__main__":
    sys.exit(main())
