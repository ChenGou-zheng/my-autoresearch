#!/usr/bin/env python3
"""Render one-time harness templates from autoresearch.config.json."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from autoresearch_common import DEFAULT_CONFIG, HARNESS_DIR, file_path, load_config, load_json


PLACEHOLDER_RE = re.compile(r"{{([A-Z0-9_]+)}}")


def markdown_list(values: list[str]) -> str:
    return "\n".join(f"- `{value}`" for value in values)


def markdown_model_list(models: dict[str, str]) -> str:
    return "\n".join(f"- `{alias}` maps to `{model}`" for alias, model in models.items())


def template_values(config_path: Path) -> dict:
    raw = load_json(config_path, default={})
    config = load_config(config_path)
    agent = config["agent"]
    experiment = dict(raw.get("experiment") or {})
    time_budget = experiment.get("time_budget_minutes", 5)
    timeout = experiment.get("timeout_minutes")
    if timeout is None:
        timeout = int(time_budget) * 2
    return {
        "TIME_BUDGET_MINUTES": str(time_budget),
        "TIMEOUT_MINUTES": str(timeout),
        "BRANCH_MODE": str(experiment.get("branch_mode", "direction")),
        "BRANCH_CLEANUP": str(experiment.get("branch_cleanup", "suggest")),
        "DEFAULT_MODEL": str(agent.get("default_model", "deepseekv4flash")),
        "DEFAULT_REASONING_EFFORT": str(agent.get("default_reasoning_effort", "xhigh")),
        "AVAILABLE_MODELS": markdown_model_list(dict(agent["available_models"])),
        "AVAILABLE_EFFORTS": markdown_list(list(agent["available_efforts"])),
    }


def render_template(template_text: str, values: dict[str, str]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            missing.add(key)
            return match.group(0)
        return values[key]

    rendered = PLACEHOLDER_RE.sub(replace, template_text)
    if missing:
        names = ", ".join(sorted(missing))
        raise SystemExit(f"missing template value(s): {names}")
    if PLACEHOLDER_RE.search(rendered):
        raise SystemExit("rendered template still contains unresolved placeholders")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Render myautoresearch init templates.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to autoresearch.config.json.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=HARNESS_DIR / "templates" / "program.md.in",
        help="Template file to render.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file. Defaults to the configured program.md path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Render and validate without writing.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    output = args.output or file_path("program", config)
    template_text = args.template.read_text(encoding="utf-8")
    rendered = render_template(template_text, template_values(args.config))

    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else None
        if current != rendered:
            print(f"{output} is out of date with {args.template}", file=sys.stderr)
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"rendered {args.template} -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
