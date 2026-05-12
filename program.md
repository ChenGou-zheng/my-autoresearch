# autoresearch

This file defines the reusable autoresearch workflow. Keep project-specific
goals, datasets, metrics, commands, and protected files in `project.md`.

## Setup

To set up a new experiment run:

1. Pick a run tag automatically if one is not supplied by the user. Default to
   today's short date tag, e.g. `may12`.
2. Create or switch to the branch `autoresearch/<tag>`. If it already exists,
   switch to it; otherwise create it from `main` or the current base branch.
3. Read `project.md` and the in-scope files listed there.
4. Initialize `results.tsv` with only the header row if it does not already
   exist. Leave it untracked when possible.
5. Proceed automatically once setup is complete.

Once setup is complete, begin experimentation.

## Session Startup

Every new agent session must begin by reading these files, in this order:

1. `program.md` - long-term operating rules.
2. `project.md` - current project objective, constraints, metrics, and commands.
3. `run_state.json` - machine-readable current state.
4. `handoff.md` - previous agent's human-readable handoff.
5. `todo.md` - short-term task queue.
6. `plan.md` - medium-term experiment plan.
7. `results.tsv` - structured experiment history, if present.
8. Relevant recent logs only as needed.

Before editing or running long commands, summarize the current best result,
last failure mode, active or blocked process, and next recommended task.

If `run_state.json`, `handoff.md`, and `todo.md` disagree, choose the
conservative action: inspect the referenced logs and artifacts first, then
update the synchronization files before launching new long work.

If `run_state.json` conflicts with the current git state, trust git as the
source of truth for code state, then update `run_state.json` to match.

If a previous session left behind partial logs or an active process, resolve
that situation before starting a new experiment.

## Synchronization Files

The autoresearch loop is designed to survive model switches and fresh sessions.
These files are the shared memory:

- `program.md`: stable reusable workflow. Change rarely.
- `project.md`: project-specific goal, metric, commands, constraints, and
  protected files.
- `plan.md`: medium-term strategy and experiment roadmap.
- `todo.md`: short-term task queue. Keep the top item actionable.
- `handoff.md`: concise narrative handoff for the next session.
- `experiment_journal.md`: detailed narrative record of experiment attempts.
- `run_state.json`: machine-readable state for scripts and agents.
- `autoresearch_setting.json`: model and reasoning setting for the next session.
- `results.tsv`: tab-separated experiment results. Keep untracked if possible.

At the end of every session, update all relevant synchronization files before
stopping. If no experiment was run, still update `handoff.md`,
`run_state.json`, and `autoresearch_setting.json` with the current status.

Use `results.tsv` for compact machine-readable scores. Use
`experiment_journal.md` for detailed reasoning and traceability. Every
non-trivial attempt should get a journal entry even if it crashes or is stopped.

When writing `results.tsv`, append new rows only. Do not rewrite or truncate the
file unless the user explicitly asks for cleanup.

## File Layout

Keep the repository root readable. Root-level files should be stable project
files, synchronization files, or assignment-required paths.

Preferred layout for new autoresearch artifacts:

- `autoresearch/logs/` - command logs from training, evaluation, rendering,
  crawling, simulations, or other project-specific jobs.
- `autoresearch/sessions/` - logs from each `opencode run` session.
- `autoresearch/tmp/` - temporary notes or scratch outputs that can be deleted.
- Project-specific output directories documented in `project.md`.

Avoid adding new root-level logs unless the project requires them. Legacy root
logs may exist; do not move them while a running process or handoff still refers
to them.

## Metrics

`project.md` must define the primary metric, how to compute it, where outputs
are written, and which secondary metrics are only proxies.

Keep primary and proxy metrics separate. A proxy metric can guide which
artifacts to inspect, but a final keep/discard decision should use the primary
metric unless `project.md` says otherwise.

## Experimentation

The goal is to improve the project-specific primary metric under the constraints
listed in `project.md`.

Each experiment should have:

- A concrete hypothesis.
- The exact files, settings, or commands changed.
- A bounded run plan or clear stopping criterion.
- A primary metric measurement when feasible.
- A keep, discard, crash, blocked, or continue decision.

Simplicity criterion: all else being equal, simpler is better. A tiny metric
gain from fragile complexity is usually not worth keeping. A tiny gain from
deleting code or simplifying the pipeline is worth keeping.

The first run should establish a baseline with the current project pipeline
before changing behavior.

## Practical Runtime Guidance

Do not assume every experiment should finish in a fixed amount of time. Prefer
staged runs:

- Smoke test: verify the code path.
- Quick comparison: run the smallest useful experiment.
- Stronger candidate: continue or rerun after a promising idea appears.

Use timeouts when appropriate, but treat timeout as a guardrail, not the
definition of a valid experiment. If a run is still improving and the idea is
promising, prefer planned checkpoints over killing it arbitrarily.

## Output And Evaluation Commands

`project.md` must define the canonical commands for:

- Running the main experiment.
- Producing the final artifact.
- Computing the primary metric.
- Extracting useful values from logs.

If a command automatically selects a latest artifact or checkpoint, verify that
it selected the intended one before trusting the score.

If generation, evaluation, or another project-specific step fails, fix the
smallest obvious issue first. Escalate to broader debugging only if the failure
repeats or the root cause is unclear.

## Logging Results

When an experiment is done, log it to `results.tsv` using tabs, not commas.
Use the project-specific header documented in `project.md`.

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

Do not commit `results.tsv` unless the project explicitly wants tracked result
history.

## Model Selection

At the end of each session, write the next-session model choice to
`autoresearch_setting.json`.

Allowed model aliases:

- `deepseekv4pro` maps to `deepseek/deepseek-v4-pro`.
- `deepseekv4flash` maps to `deepseek/deepseek-v4-flash`.

Allowed reasoning variants:

- `medium`
- `high`
- `xhigh`
- `max`

Use `deepseekv4pro` with `max` for:

- Complex debugging.
- Environment failures.
- Architecture design or major strategy changes.
- Confusing metric behavior or repeated regressions.
- Two consecutive crashes or blocked runs.

Use `deepseekv4flash` with `xhigh` or `max` for:

- Running already planned experiments.
- Implementing a clearly specified preprocessing, parameter, or pipeline change.
- Producing artifacts and evaluating the primary metric.
- Updating logs and synchronization files.

Use `deepseekv4flash` with `medium` or `high` for:

- Documentation cleanup.
- Result summarization.
- Simple queue maintenance.

Recommended JSON shape:

```json
{
  "next_model": "deepseekv4flash",
  "next_reasoning_effort": "xhigh",
  "expected_work_type": "experiment",
  "next_task": "Run the next planned comparison and evaluate the primary metric.",
  "reason": "The next task is an already specified experiment.",
  "prompt": "Read program.md first. Then read project.md, run_state.json, handoff.md, todo.md, plan.md, and results.tsv. Summarize current best result, active or blocked state, and next concrete action before editing or running long commands. Continue exactly one autoresearch loop iteration unless blocked.",
  "updated_at": "2026-05-12T00:00:00+08:00"
}
```

The external runner reads this file and launches:

```bash
opencode run -m '<resolved model>' --variant '<next_reasoning_effort>' '<prompt>'
```

If the model alias is unknown, the runner may pass it through as a raw model
name. Keep aliases consistent unless there is a clear reason to use a raw name.

If the next session type is ambiguous, prefer the safer, higher-capability
choice:

- `deepseekv4pro + max` for debugging, regressions, or architecture changes.
- `deepseekv4flash + xhigh` for concrete experiment execution.

## The Experiment Loop

The experiment runs on a dedicated branch, e.g. `autoresearch/may12`.

LOOP:

1. Inspect git state and the current best result.
2. Form one concrete experimental idea.
3. Edit project files, configuration, or command settings as needed.
4. If the experiment changes tracked code or configuration, commit or otherwise
   clearly isolate those changes before running the long experiment.
5. Run the experiment with redirected logs.
6. If it crashes, inspect the relevant log tail. Fix simple bugs and rerun;
   otherwise record a crash and move on.
7. Inspect proxy metrics or intermediate artifacts when available.
8. Produce the final artifact required by `project.md`.
9. Run the primary evaluation command from `project.md`.
10. Extract the primary metric and record the result in `results.tsv`.
11. If the primary metric improves, keep the experiment state and advance from
    it.
12. If the primary metric is equal or worse, mark the attempt as `discard`.
    Revert only changes that clearly belong to that failed experiment and are no
    longer useful. Keep logs, artifacts, and result history. Do not use
    destructive git commands unless the user explicitly asks.
13. Update `todo.md`, `plan.md` if strategy changed, `handoff.md`,
    `experiment_journal.md`, `run_state.json`, and
    `autoresearch_setting.json`.
14. End the current session. The external runner may start a new session with
    the selected model and reasoning variant.

Do not reset or discard unrelated user changes. Only revert your own experiment
changes when the experiment is judged worse or broken.

## Active Process State

Long-running jobs should be recorded in `run_state.json` so the supervisor and
future agents can wait or recover.

Preferred shape:

```json
{
  "active": true,
  "last_status": "running",
  "active_process": {
    "pid": 12345,
    "kind": "training",
    "log_path": "autoresearch/logs/example.log",
    "expected_output": "path/to/expected/artifact",
    "started_at": "2026-05-12T00:00:00+08:00"
  }
}
```

Use `active_process.kind` values that match the project, such as `training`,
`evaluation`, `render`, `crawl`, `simulation`, or `generation`.

For compatibility with older files, `training_pid` may still be present, but
new updates should prefer `active_process.pid`.

## End-Of-Session Handoff

Before stopping, ensure `handoff.md` includes:

- Current best result, commit if relevant, artifact, and settings.
- What changed in the last session.
- Commands run and where logs were written.
- Results or crash details.
- The next recommended task and why.
- Warnings for the next session.

Before stopping, ensure `experiment_journal.md` has an entry for each meaningful
attempt. Include hypothesis, changed files/settings, commands, logs, artifacts,
primary metric, proxy metrics, decision, and follow-up.

Ensure `run_state.json` includes at least:

- Whether a session is active.
- Last session id and timestamp.
- Current branch.
- Best result and commit if relevant.
- Last status: `not_started`, `running`, `keep`, `discard`, `crash`, or
  `blocked`.
- Consecutive crash count.
- Selected next task.
- Active process details when a long job is running.

If a session is interrupted mid-run, set `last_status` to `blocked` or
`running` as appropriate, and leave enough detail in `handoff.md` for recovery.

Ensure `todo.md` has a clear top task, and `autoresearch_setting.json` has the
next model and reasoning variant.

## Autonomous Operation

After the run begins, continue the experiment loop without asking whether to
keep going. Stop only if interrupted, blocked by missing resources, or the
machine cannot run the required commands.

For true unattended operation, run `scripts/autoresearch_supervisor.py` instead
of launching `scripts/autoresearch_next.py` manually. The supervisor handles the
case where an agent session exits after starting a background process: it waits
for the recorded `active_process.pid` to finish, then starts the next
`opencode run` session from `autoresearch_setting.json`.
