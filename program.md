# autoresearch Program

This file defines the reusable autoresearch workflow. Keep project-specific
goals, metrics, commands, paths, and protected files in `project.md`.

## Roles

- `program.md`: generic process. Change rarely.
- `project.md`: host project contract. Edit for each project.
- `autoresearch.config.json`: stable script configuration.
- `next_run.json`: launch plan for the next agent session.
- `run_state.json`: machine-readable current state.
- `handoff.md`: concise state for the next session.
- `todo.md`: short-term task queue.
- `plan.md`: medium-term strategy.
- `experiment_journal.md`: detailed attempt history.
- `results.tsv`: compact result table.

## Startup

Every new agent session must begin by reading these files, in this order:

1. `myautoresearch/program.md`
2. `myautoresearch/project.md`
3. `myautoresearch/run_state.json`
4. `myautoresearch/handoff.md`
5. `myautoresearch/todo.md`
6. `myautoresearch/plan.md`
7. `myautoresearch/results.tsv`
8. Relevant recent logs only as needed.

Treat the parent directory as the project workspace unless
`autoresearch.config.json` says otherwise.

Before editing or running long commands, summarize:

- current project objective;
- current best result, if any;
- active or blocked process state;
- next concrete action.

If state files disagree, inspect logs and git state first, then update the
synchronization files before launching new long work.

## Project Contract

`project.md` must define:

- the objective;
- in-scope files;
- protected files;
- the primary metric and exact evaluation command;
- secondary signals or proxy metrics;
- setup, smoke-test, experiment, and evaluation commands;
- output paths and artifacts;
- project-specific constraints.

Do not infer protected-file rules from memory when `project.md` is unclear.
Ask or stop with `blocked` if modifying a file could violate project
constraints.

## Experiment Loop

Each loop should do one bounded unit of work:

1. Inspect current state and git changes.
2. Pick one concrete hypothesis or maintenance task.
3. Make the smallest useful change.
4. Run the smallest useful validation first.
5. Run the project metric when feasible.
6. Record the result in `results.tsv`.
7. Add details to `experiment_journal.md`.
8. Update `handoff.md`, `todo.md`, `plan.md` if needed, `run_state.json`, and
   `next_run.json`.
9. End the session.

The first run in a new project should establish or verify a baseline before
changing behavior.

## Results

Use tab-separated rows in `results.tsv`. Append rows only unless the user asks
for cleanup.

Recommended generic columns:

```text
commit	primary_metric	secondary_metric	runtime_or_cost	status	description
```

Status values:

- `keep`: improves or meaningfully advances the current best result.
- `discard`: measured and not worth continuing.
- `crash`: failed due to an execution error.
- `blocked`: cannot proceed without missing resources or user action.
- `continue`: partial result that should be continued before judging.

Primary metrics decide keep/discard unless `project.md` explicitly says
otherwise. Proxy metrics are only guidance.

## Runtime Guidance

Prefer staged runs:

- smoke test: verify the path works;
- quick comparison: smallest useful experiment;
- stronger candidate: longer or more expensive run after a promising signal.

Use timeouts as guardrails, not as the definition of success. If a long job
continues after the agent exits, record it in `run_state.json`.

## Active Process State

Long-running jobs should be recorded in `run_state.json`:

```json
{
  "active": true,
  "last_status": "running",
  "active_process": {
    "pid": 12345,
    "kind": "training",
    "log_path": "myautoresearch/autoresearch/logs/example.log",
    "expected_output": "path/to/expected/artifact",
    "started_at": "2026-05-14T00:00:00+08:00"
  }
}
```

Use `active_process.kind` values that match the project, such as `training`,
`evaluation`, `render`, `crawl`, `simulation`, `generation`, or `test`.

For compatibility with older state files, `training_pid` may exist. New updates
should use `active_process.pid`.

## Model Selection

At the end of each session, update `next_run.json`.

Allowed model aliases:

- `deepseekv4pro` maps to `deepseek/deepseek-v4-pro`.
- `deepseekv4flash` maps to `deepseek/deepseek-v4-flash`.

Allowed reasoning variants:

- `medium`
- `high`
- `xhigh`
- `max`

Use a stronger model and variant for confusing failures, architecture changes,
or repeated regressions. Use a faster model for routine experiment execution or
state maintenance.

Recommended `next_run.json` shape:

```json
{
  "next_model": "deepseekv4flash",
  "next_reasoning_effort": "xhigh",
  "expected_work_type": "experiment",
  "next_task": "Run the next planned comparison and evaluate the primary metric.",
  "reason": "The next task is a specified experiment.",
  "prompt": "Read myautoresearch/program.md first. Then read myautoresearch/project.md, myautoresearch/run_state.json, myautoresearch/handoff.md, myautoresearch/todo.md, myautoresearch/plan.md, and myautoresearch/results.tsv. Treat the parent directory as the project workspace. Summarize current best result, active or blocked state, and next concrete action before editing or running long commands. Continue exactly one autoresearch loop iteration unless blocked.",
  "updated_at": "2026-05-14T00:00:00+08:00"
}
```

## Handoff

Before stopping, ensure `handoff.md` includes:

- current best result, commit, artifact, and settings if relevant;
- what changed in the last session;
- commands run and logs written;
- results or crash details;
- next recommended task;
- warnings for the next session.

If no experiment was run, still update `handoff.md`, `run_state.json`, and
`next_run.json` with the current status.

## Safety

Do not reset or discard unrelated user changes. Only revert changes that clearly
belong to the failed experiment and are no longer useful. Do not use destructive
git commands unless the user explicitly asks.

Stop with `blocked` when required resources, credentials, data, or user
decisions are missing.
