"""Shared helpers for the autoresearch harness scripts."""

from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import time
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = HARNESS_DIR / "autoresearch.config.json"
DEFAULT_NEXT_RUN = HARNESS_DIR / "next_run.json"
LEGACY_SETTINGS = HARNESS_DIR / "autoresearch_setting.json"
DEFAULT_STATE = HARNESS_DIR / "run_state.json"
DEFAULT_INBOX = HARNESS_DIR / "autoresearch" / "inbox.jsonl"
DEFAULT_FILES = {
    "program": "program.md",
    "project": "project.md",
    "state": "run_state.json",
    "todo": "todo.md",
    "plan": "plan.md",
    "handoff": "handoff.md",
    "journal": "experiment_journal.md",
    "results": "results.tsv",
    "next_run": "next_run.json",
    "inbox": "autoresearch/inbox.jsonl",
}

MODEL_ALIASES = {
    "deepseekv4pro": "deepseek/deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseekv4flash": "deepseek/deepseek-v4-flash",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-flash": "deepseek/deepseek-v4-flash",
}

ALLOWED_VARIANTS = {"medium", "high", "xhigh", "max"}
DEFAULT_SUPERVISOR = {
    "opencode_timeout_seconds": 3600,
    "active_process_stale_seconds": 7200,
    "kill_grace_seconds": 15,
}
DEFAULT_PROMPT = (
    "Read myautoresearch/program.md first. Then read myautoresearch/project.md, "
    "myautoresearch/run_state.json, myautoresearch/handoff.md, "
    "myautoresearch/todo.md, myautoresearch/plan.md, and "
    "myautoresearch/results.tsv. Treat the parent directory as the project "
    "workspace. Summarize current best result, active or blocked state, and next "
    "concrete action before editing or running long commands. Continue exactly "
    "one autoresearch loop iteration unless blocked."
)


def _resolve_path(raw_path: str | Path, base: Path = HARNESS_DIR) -> Path:
    path = Path(os.path.expanduser(str(raw_path)))
    if not path.is_absolute():
        path = base / path
    return path.resolve()


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


def process_status(pid: int | None) -> str:
    """Return dead, alive, or zombie for a local process id."""
    if not pid or pid <= 0:
        return "dead"

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "alive"

    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        stat_text = proc_stat.read_text(encoding="utf-8")
    except OSError:
        stat_text = ""

    if stat_text:
        try:
            state = stat_text.rsplit(") ", 1)[1].split()[0]
        except IndexError:
            state = ""
        if state == "Z":
            return "zombie"
        if state:
            return "alive"

    try:
        stat = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "stat="],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "alive"
    if stat.startswith("Z"):
        return "zombie"
    return "alive" if stat else "dead"


def pid_alive(pid: int | None) -> bool:
    return process_status(pid) == "alive"


def terminate_process_group(pid: int | None, grace_seconds: int = 15) -> dict:
    """Terminate a process or process group, escalating to SIGKILL if needed."""
    result = {
        "pid": pid,
        "sent_term": False,
        "sent_kill": False,
        "terminated": False,
    }
    if not pid or process_status(pid) != "alive":
        result["terminated"] = True
        return result

    sent_any = False
    try:
        os.killpg(pid, signal.SIGTERM)
        sent_any = True
    except ProcessLookupError:
        pass
    except (PermissionError, OSError):
        pass
    try:
        os.kill(pid, signal.SIGTERM)
        sent_any = True
    except ProcessLookupError:
        result["terminated"] = True
        return result
    except (PermissionError, OSError):
        pass
    result["sent_term"] = sent_any
    if not sent_any:
        return result

    deadline = time.monotonic() + max(0, grace_seconds)
    while time.monotonic() < deadline:
        if process_status(pid) != "alive":
            result["terminated"] = True
            return result
        time.sleep(0.2)

    if process_status(pid) != "alive":
        result["terminated"] = True
        return result

    sent_any = False
    try:
        os.killpg(pid, signal.SIGKILL)
        sent_any = True
    except ProcessLookupError:
        pass
    except (PermissionError, OSError):
        pass
    try:
        os.kill(pid, signal.SIGKILL)
        sent_any = True
    except ProcessLookupError:
        result["terminated"] = True
        return result
    except (PermissionError, OSError):
        pass
    result["sent_kill"] = sent_any
    if not sent_any:
        return result

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if process_status(pid) != "alive":
            result["terminated"] = True
            return result
        time.sleep(0.2)
    result["terminated"] = process_status(pid) != "alive"
    return result


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    config = load_json(path, default={})
    workspace_dir = _resolve_path(config.get("workspace_dir", ".."))
    state_dir = _resolve_path(config.get("state_dir", "."))
    files = DEFAULT_FILES | dict(config.get("files") or {})
    agent = dict(config.get("agent") or {})
    agent["available_models"] = dict(agent.get("available_models") or MODEL_ALIASES)
    agent["available_efforts"] = list(agent.get("available_efforts") or sorted(ALLOWED_VARIANTS))
    supervisor = DEFAULT_SUPERVISOR | dict(config.get("supervisor") or {})
    return {
        "workspace_dir": workspace_dir,
        "state_dir": state_dir,
        "files": files,
        "agent": agent,
        "supervisor": supervisor,
    }


def file_path(name: str, config: dict | None = None) -> Path:
    config = config or load_config()
    files = config["files"]
    if name not in files:
        raise SystemExit(f"unknown configured file key: {name}")
    return _resolve_path(files[name], config["state_dir"])


def next_run_path(config: dict | None = None) -> Path:
    config = config or load_config()
    configured = file_path("next_run", config)
    if configured.exists() or not LEGACY_SETTINGS.exists():
        return configured
    return LEGACY_SETTINGS


def inbox_path(config: dict | None = None) -> Path:
    return file_path("inbox", config)


def workspace_dir(config: dict | None = None) -> Path:
    config = config or load_config()
    return config["workspace_dir"]


def resolve_model(raw_model: str, config: dict | None = None) -> str:
    model = raw_model.strip()
    config = config or load_config()
    aliases = dict((config.get("agent") or {}).get("available_models") or MODEL_ALIASES)
    return aliases.get(model, model)


def resolve_variant(raw_variant: str, config: dict | None = None) -> str:
    variant = raw_variant.strip()
    config = config or load_config()
    allowed_variants = set((config.get("agent") or {}).get("available_efforts") or ALLOWED_VARIANTS)
    if variant not in allowed_variants:
        allowed = ", ".join(sorted(allowed_variants))
        raise SystemExit(f"unsupported variant {variant!r}; expected one of: {allowed}")
    return variant


def build_opencode_command(
    settings: dict,
    prompt_override: str | None = None,
    config: dict | None = None,
) -> list[str]:
    config = config or load_config()
    raw_model = settings.get("next_model")
    raw_variant = settings.get("next_reasoning_effort")
    if not raw_model:
        raise SystemExit("next_run.json is missing next_model")
    if not raw_variant:
        raise SystemExit("next_run.json is missing next_reasoning_effort")

    model = resolve_model(str(raw_model), config)
    variant = resolve_variant(str(raw_variant), config)
    prompt = prompt_override or str(settings.get("prompt") or DEFAULT_PROMPT)
    agent = config.get("agent") or {}
    command = str(settings.get("agent_command") or agent.get("command") or "opencode")
    return [command, "run", "-m", model, "--variant", variant, prompt]


def build_opencode_command_with_controls(
    settings: dict,
    prompt_override: str | None = None,
    consume_controls: bool = True,
    config: dict | None = None,
) -> tuple[list[str], bool, list[dict]]:
    from autoresearch_control import apply_pending_events

    cmd = build_opencode_command(settings, prompt_override, config)
    cmd[-1], should_stop_after, events = apply_pending_events(
        cmd[-1],
        consume=consume_controls,
    )
    return cmd, should_stop_after, events


def format_command(cmd: list[str]) -> str:
    return shlex.join(cmd)
