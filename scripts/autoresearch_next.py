#!/usr/bin/env python3
"""Launch the next autoresearch session from autoresearch_setting.json."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS = PROJECT_DIR / "autoresearch_setting.json"

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


def load_settings(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"settings file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def resolve_model(raw_model: str) -> str:
    key = raw_model.strip()
    return MODEL_ALIASES.get(key, key)


def resolve_variant(raw_variant: str) -> str:
    variant = raw_variant.strip()
    if variant not in ALLOWED_VARIANTS:
        allowed = ", ".join(sorted(ALLOWED_VARIANTS))
        raise SystemExit(f"unsupported variant {variant!r}; expected one of: {allowed}")
    return variant


def build_command(settings: dict, prompt_override: str | None) -> list[str]:
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
    cmd = build_command(settings, args.prompt)

    print(" ".join(repr(part) if " " in part else part for part in cmd))
    if args.dry_run:
        return 0

    return subprocess.run(cmd, cwd=PROJECT_DIR).returncode


if __name__ == "__main__":
    sys.exit(main())
