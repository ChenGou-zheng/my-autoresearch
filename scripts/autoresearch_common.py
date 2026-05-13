"""Shared helpers for the autoresearch harness scripts."""

from __future__ import annotations

import json
import shlex
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS = PROJECT_DIR / "autoresearch_setting.json"
DEFAULT_STATE = PROJECT_DIR / "run_state.json"

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


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        if default is not None:
            return default
        raise SystemExit(f"missing required file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
