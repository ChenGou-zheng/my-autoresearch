"""Target-based termination helpers for the autoresearch supervisor."""

from __future__ import annotations

import csv
from pathlib import Path

from autoresearch_common import file_path, load_json, write_json
from autoresearch_control import append_event, pending_events
from supervisor.state import now


def parse_metric(raw: object) -> float | None:
    try:
        text = str(raw).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_metric(value: float, termination: dict) -> float:
    if str(termination.get("scale") or "unit").lower() == "percent":
        return value / 100.0
    return value


def normalized_target(termination: dict) -> float | None:
    target = parse_metric(termination.get("target"))
    if target is None:
        return None
    return normalize_metric(target, termination)


def termination_results_path(termination: dict, config: dict) -> Path:
    key = str(termination.get("results_file") or "results")
    if key in config["files"]:
        return file_path(key, config)
    path = Path(key).expanduser()
    if not path.is_absolute():
        path = config["state_dir"] / path
    return path.resolve()


def best_result_metric(termination: dict, config: dict) -> tuple[float | None, dict | None]:
    path = termination_results_path(termination, config)
    if not path.exists():
        return None, None

    metric_column = str(termination.get("metric_column") or "primary_metric")
    eligible = set(termination.get("eligible_statuses") or ["keep", "continue"])
    best_metric: float | None = None
    best_row: dict | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or metric_column not in reader.fieldnames:
            return None, None
        for row in reader:
            status = str(row.get("status") or "").strip()
            if eligible and status not in eligible:
                continue
            metric = parse_metric(row.get(metric_column))
            if metric is None:
                continue
            metric = normalize_metric(metric, termination)
            if best_metric is None or metric > best_metric:
                best_metric = metric
                best_row = row
    return best_metric, best_row


def queue_target_finish_if_needed(config: dict, state_path: Path, dry_run: bool) -> bool:
    termination = config.get("termination") or {}
    mode = str(termination.get("mode") or "manual").lower()
    if mode in {"manual", "off", "never"}:
        return False

    target = normalized_target(termination)
    if target is None:
        return False

    state = load_json(state_path, default={})
    recorded = state.get("termination")
    if isinstance(recorded, dict) and recorded.get("finalization_started"):
        print(f"[{now()}] target finalization already started; stopping supervisor loop")
        return True

    best_metric, best_row = best_result_metric(termination, config)
    if best_metric is None or best_metric < target:
        return False

    message = (
        f"Target reached: {termination.get('metric_column', 'primary_metric')} "
        f"{best_metric:g} >= {target:g}. Do final synchronization and stop."
    )
    if termination.get("finalize_with_agent") is False:
        print(f"[{now()}] target reached; stopping without final agent session: {message}")
        if not dry_run:
            state["termination"] = {
                "target_reached": True,
                "finalization_started": False,
                "finalization_completed": True,
                "best_result": best_metric,
                "target": target,
                "source": str(termination_results_path(termination, config)),
                "matched_row": best_row,
                "reason": message,
                "completed_at": now(),
            }
            write_json(state_path, state)
        return True

    if any(event.get("type") == "finish" and not event.get("consumed_at") for event in pending_events()):
        print(f"[{now()}] target reached; pending finish event already exists")
    elif dry_run:
        print(f"[{now()}] target reached; would queue finish event: {message}")
    else:
        event = append_event("finish", message, force=False)
        print(f"[{now()}] target reached; queued finish event {event['id'][:8]}")

    if not dry_run:
        state["termination"] = {
            "target_reached": True,
            "finalization_started": True,
            "finalization_completed": False,
            "best_result": best_metric,
            "target": target,
            "source": str(termination_results_path(termination, config)),
            "matched_row": best_row,
            "reason": message,
            "updated_at": now(),
        }
        write_json(state_path, state)
    return False


def mark_target_finalization_completed(state_path: Path, return_code: int) -> None:
    state = load_json(state_path, default={})
    termination = state.get("termination")
    if not isinstance(termination, dict) or not termination.get("finalization_started"):
        return
    if return_code == 0:
        termination["finalization_completed"] = True
        termination["completed_at"] = now()
    else:
        termination["finalization_completed"] = False
        termination["finalization_failed"] = True
        termination["failed_at"] = now()
    termination["finalization_return_code"] = return_code
    state["termination"] = termination
    write_json(state_path, state)
