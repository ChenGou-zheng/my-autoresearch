# myautoresearch

`myautoresearch` is a reusable autoresearch harness meant to live inside an
existing project as a subdirectory.

It is inspired by [karpathy's autoresearch](https://github.com/karpathy/autoresearch)
and wraps the same iterative idea with explicit context files, launch settings,
session handoff, and lightweight process supervision.

Typical layout:

```text
host-project/
  myautoresearch/
    program.md
    project.md
    autoresearch.config.json
    next_run.json
    scripts/
  src/
  ...
```

The harness keeps agent memory, run state, logs, and launch settings under
`myautoresearch/`, while the agent works in the parent project directory.

## Contents

- [Get Started](#get-started)
- [Files To Edit](#files-to-edit)
- [Init Templates](#init-templates)
- [State Files](#state-files)
- [Supervisor And TUI](#supervisor-and-tui)
- [Configuration](#configuration)
- [Next Run](#next-run)
- [Run Logic](#run-logic)

## Get Started

From an existing project root:

```bash
git clone <repo-url> myautoresearch
```

Edit the project-specific files yourself, or ask an agent to fill them in:

- `myautoresearch/project.md`: objective, metric, commands, protected files.
- `myautoresearch/todo.md`: first concrete task, if needed.
- `myautoresearch/autoresearch.config.json`: paths or model defaults, if the
  defaults are not enough.

```bash
python3 myautoresearch/scripts/init_harness.py
python3 myautoresearch/scripts/autoresearch_next.py --dry-run
python3 myautoresearch/scripts/autoresearch_next.py
```

Use `scripts/autoresearch_supervisor.py` instead when you want the loop to keep
starting new sessions after the previous one finishes.

## Files To Edit

For a new project, usually edit only these files:

- `project.md`: project objective, metric, commands, protected files, and output
  paths.
- `todo.md`: the first concrete task, if the default task is not enough.
- `autoresearch.config.json`: workspace path, file names, or default model
  settings.
- `opencode.json`: permission rules, if the project has files that need hard
  protection.

Do not normally edit `program.md` directly. Edit `templates/program.md.in` for
workflow text that should apply to future generated copies, or edit
`autoresearch.config.json` for install-time options.

## Init Templates

`program.md` is generated from `templates/program.md.in` by
`scripts/init_harness.py`. The template uses simple `{{NAME}}` placeholders and
the script performs one-time text replacement during init/install. The generated
`program.md` is ordinary Markdown; runtime agents should not see unresolved
template placeholders.

Run this after changing install-time options in `autoresearch.config.json`:

```bash
python3 myautoresearch/scripts/init_harness.py
```

Use check mode in CI or before committing template changes:

```bash
python3 myautoresearch/scripts/init_harness.py --check
```

Keep frequently changing project details in `project.md`. Keep machine-readable
runtime settings in `autoresearch.config.json`.

## State Files

- `program.md`: generic autoresearch process and operating rules.
- `project.md`: project-specific contract.
- `next_run.json`: model, reasoning effort, prompt, and task for the next agent
  session.
- `run_state.json`: machine-readable current state.
- `handoff.md`: short human-readable handoff.
- `plan.md`: medium-term strategy.
- `todo.md`: short-term task queue.
- `experiment_journal.md`: detailed attempt history.
- `results.tsv`: compact result table.
- `autoresearch/logs/`: project command logs.
- `autoresearch/sessions/`: `opencode run` session logs.
- `autoresearch/tmp/`: disposable scratch files.

## Supervisor And TUI

The supervisor and TUI communicate through files under `myautoresearch/`. The
TUI is not the process manager and does not need to stay open.

Run the supervisor in a persistent shell, `tmux`, or the background:

```bash
python3 myautoresearch/scripts/autoresearch_supervisor.py
```

Open the TUI only when you want to inspect status, tail recent logs, or queue a
control event:

```bash
python3 myautoresearch/scripts/autoresearch_tui.py
```

TUI keys:

- `s`: queue a suggestion for the next run.
- `S`: queue a suggestion and interrupt the recorded session or process.
- `f`: queue a finish request for the next run.
- `F`: queue a finish request and interrupt the recorded session or process.
- `q`: quit the TUI.

Closing the TUI does not stop the supervisor or any recorded project process.
Force actions work by reading pids from `run_state.json` and sending a signal.

## Configuration

`autoresearch.config.json` controls paths and defaults:

```json
{
  "workspace_dir": "..",
  "state_dir": ".",
  "agent": {
    "command": "opencode",
    "default_model": "deepseekv4flash",
    "default_reasoning_effort": "xhigh"
  },
  "experiment": {
    "time_budget_minutes": 5,
    "timeout_minutes": 10,
    "branch_mode": "direction",
    "branch_cleanup": "suggest"
  },
  "files": {
    "program": "program.md",
    "project": "project.md",
    "state": "run_state.json",
    "todo": "todo.md",
    "plan": "plan.md",
    "handoff": "handoff.md",
    "journal": "experiment_journal.md",
    "results": "results.tsv",
    "next_run": "next_run.json"
  }
}
```

`workspace_dir` is resolved relative to `myautoresearch/`. The default `..`
means the agent runs from the parent project directory.

`experiment.time_budget_minutes` and `experiment.timeout_minutes` are rendered
into `program.md` during init. `branch_mode: "direction"` means new research
directions should get their own `autoresearch/<tag>-<direction>` branch, while
small follow-up tweaks stay on the current direction branch. `branch_cleanup:
"suggest"` means agents should list cleanup candidates instead of deleting
branches automatically.

## Next Run

`next_run.json` is the launch plan for the next agent session:

```json
{
  "next_model": "deepseekv4flash",
  "next_reasoning_effort": "xhigh",
  "expected_work_type": "setup",
  "next_task": "Inspect the parent project and prepare the first concrete research task.",
  "reason": "A new harness should understand the host project first.",
  "prompt": "Read myautoresearch/program.md first...",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

The scripts still fall back to the old `autoresearch_setting.json` name if
`next_run.json` is missing, but new projects should use `next_run.json`.

## Run Logic

The harness is a small file-based loop around short `opencode run` sessions:

```mermaid
flowchart LR
    A["Edit project.md / todo.md"] --> B["Launch one run"]
    B --> C["Agent reads program, project, state, handoff, todo, plan, results"]
    C --> D["Agent works in parent project"]
    D --> E["Agent updates run_state, handoff, results, next_run"]
    E --> F{"Continue?"}
    F -->|"manual"| B
    F -->|"supervisor"| G["Wait for active process if needed"]
    G --> B
    T["TUI"] --> E
    T --> B
```

`autoresearch_next.py` launches exactly one configured session from
`next_run.json`.

`autoresearch_supervisor.py` repeats that launch step. Before each cycle, it
reads `run_state.json`; if `active_process.pid` is alive and `last_status` is
`running`, it waits. Otherwise it launches the next session and writes a log
under `autoresearch/sessions/`.

`autoresearch_tui.py` reads the same state files and log files. It can also
append user control events to `autoresearch/inbox.jsonl`; the next launch folds
those events into the agent prompt.

Long-running project jobs should be recorded in this shape:

```json
{
  "active": true,
  "last_status": "running",
  "active_process": {
    "pid": 12345,
    "kind": "training",
    "log_path": "myautoresearch/autoresearch/logs/run.log",
    "expected_output": "path/to/artifact",
    "started_at": "2026-05-14T00:00:00+08:00"
  }
}
```
