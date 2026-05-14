# myautoresearch

`myautoresearch` is a reusable autoresearch harness meant to live inside an
existing project as a subdirectory.

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

## Get Started

From an existing project root, clone or copy this repository as
`myautoresearch`:

```bash
git clone <repo-url> myautoresearch
```

Fill in the short project contract:

```bash
$EDITOR myautoresearch/project.md
```

At minimum, define the objective, protected files, the main validation or
evaluation command, and the first useful task. Then inspect the launch command:

```bash
python3 myautoresearch/scripts/autoresearch_next.py --dry-run
```

If the command looks right, start one bounded agent session:

```bash
python3 myautoresearch/scripts/autoresearch_next.py
```

The default `autoresearch.config.json` already points the agent at the parent
project directory with `"workspace_dir": ".."`, so most projects only need
`project.md` and possibly `todo.md` edited before the first run.

## Files To Edit

For a new project, usually edit only these files:

- `project.md`: project objective, metric, commands, protected files, and output
  paths.
- `todo.md`: the first concrete task, if the default task is not enough.
- `autoresearch.config.json`: workspace path, file names, or default model
  settings.
- `opencode.json`: permission rules, if the project has files that need hard
  protection.

Do not normally edit `program.md`; it is the reusable workflow.

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

## Usage

From the parent project directory:

```bash
git clone <repo-url> myautoresearch
```

Then edit `myautoresearch/project.md` and run one agent session:

```bash
python3 myautoresearch/scripts/autoresearch_next.py
```

For unattended cycling:

```bash
python3 myautoresearch/scripts/autoresearch_supervisor.py
```

To inspect without launching a run:

```bash
python3 myautoresearch/scripts/autoresearch_next.py --dry-run
```

To watch status and queue control events:

```bash
python3 myautoresearch/scripts/autoresearch_tui.py
```

TUI keys:

- `s`: queue a suggestion for the next run.
- `S`: queue a suggestion and interrupt the recorded session or process.
- `f`: queue a finish request for the next run.
- `F`: queue a finish request and interrupt the recorded session or process.
- `q`: quit the TUI.

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

## Supervisor

The supervisor reads `run_state.json`. If `active_process.pid` is alive and
`last_status` is `running`, it waits. Otherwise it launches the next configured
`opencode run` session and writes a log under `autoresearch/sessions/`.

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
