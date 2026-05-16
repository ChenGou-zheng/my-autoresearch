"""User control events for the autoresearch loop."""

from __future__ import annotations

import datetime as dt
import json
import signal
import uuid
from pathlib import Path

from autoresearch_common import inbox_path, pid_alive, write_json


INBOX_PATH = inbox_path()


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_events(path: Path = INBOX_PATH) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def write_events(events: list[dict], path: Path = INBOX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events)
    path.write_text(text, encoding="utf-8")


def append_event(event_type: str, message: str, force: bool = False) -> dict:
    if event_type not in {"suggest", "finish"}:
        raise ValueError(f"unsupported control event type: {event_type}")
    event = {
        "id": uuid.uuid4().hex,
        "type": event_type,
        "force": bool(force),
        "message": message.strip(),
        "created_at": now(),
        "consumed_at": None,
    }
    events = read_events()
    events.append(event)
    write_events(events)
    return event


def pending_events() -> list[dict]:
    return [event for event in read_events() if not event.get("consumed_at")]


def mark_consumed(consumed: list[dict]) -> None:
    if not consumed:
        return
    consumed_ids = {event.get("id") for event in consumed}
    consumed_at = now()
    events = read_events()
    for event in events:
        if event.get("id") in consumed_ids:
            event["consumed_at"] = consumed_at
    write_events(events)


def render_events_for_prompt(events: list[dict]) -> str:
    if not events:
        return ""

    lines = [
        "",
        "## User Control Events",
        "",
        "Apply these user messages in this session. They were entered from the autoresearch TUI.",
    ]
    has_finish = any(event.get("type") == "finish" for event in events)
    if has_finish:
        lines.extend(
            [
                "",
                "At least one event is type `finish`: do a concise final synchronization pass, update handoff/run_state/next_run/results or notes as appropriate, avoid launching new long experiments, and then exit cleanly.",
            ]
        )

    for index, event in enumerate(events, start=1):
        event_type = event.get("type", "suggest")
        force = " force=true" if event.get("force") else ""
        message = str(event.get("message") or "").strip()
        lines.append("")
        lines.append(f"{index}. type={event_type}{force}")
        if message:
            lines.append(message)
        else:
            lines.append("(no additional user message)")
    return "\n".join(lines)


def apply_pending_events(prompt: str, consume: bool = True) -> tuple[str, bool, list[dict]]:
    events = pending_events()
    event_prompt = render_events_for_prompt(events)
    combined_prompt = prompt + event_prompt if event_prompt else prompt
    should_stop_after = any(event.get("type") == "finish" for event in events)
    if consume:
        mark_consumed(events)
    return combined_prompt, should_stop_after, events


def kill_pid(pid: int | None) -> bool:
    if not pid_alive(pid):
        return False
    assert pid is not None
    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
        return True


def active_pids(state: dict) -> list[int]:
    pids: list[int] = []
    opencode_session = state.get("opencode_session")
    if isinstance(opencode_session, dict):
        pids.append(_as_pid(opencode_session.get("pid")))

    active_process = state.get("active_process")
    if isinstance(active_process, dict):
        pids.append(_as_pid(active_process.get("pid")))
    pids.append(_as_pid(state.get("training_pid")))
    return [pid for pid in pids if pid]


def _as_pid(raw: object) -> int | None:
    try:
        pid = int(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return pid if pid and pid > 0 else None


def interrupt_from_state(state_path: Path) -> list[int]:
    from autoresearch_common import load_json

    state = load_json(state_path, default={})
    killed: list[int] = []
    for pid in active_pids(state):
        if kill_pid(pid):
            killed.append(pid)
    if killed:
        state["last_status"] = "interrupted"
        state["last_updated"] = now()
        state["interrupted_by_user"] = {"pids": killed, "at": now()}
        state["opencode_session"] = None
        active_process = state.get("active_process")
        if isinstance(active_process, dict) and _as_pid(active_process.get("pid")) in killed:
            state["active_process"] = None
        if _as_pid(state.get("training_pid")) in killed:
            state["training_pid"] = None
        if not state.get("active_process") and not state.get("training_pid"):
            state["active"] = False
        write_json(state_path, state)
    return killed
