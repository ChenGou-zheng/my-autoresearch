# autoresearch Template

This folder contains a reusable autoresearch loop for running iterative
experiments across multiple agent sessions.

## Files

- `program.md`: reusable workflow rules.
- `project.md`: project-specific objective, metrics, commands, and constraints.
- `plan.md`: medium-term experiment strategy.
- `todo.md`: short-term task queue.
- `handoff.md`: concise state for the next session.
- `experiment_journal.md`: detailed experiment history.
- `run_state.json`: machine-readable current state.
- `autoresearch_setting.json`: next model, reasoning effort, and startup prompt.
- `results.tsv`: compact result table.

## Usage

1. Copy this folder into a project.
2. Edit `project.md` for that project.
3. Set the first task in `todo.md`.
4. Run one session:

```bash
uv run python scripts/autoresearch_next.py
```

For unattended cycling, use:

```bash
uv run python scripts/autoresearch_supervisor.py
```

The supervisor waits for `run_state.json.active_process.pid` when a long job is
running, then launches the next configured session.
