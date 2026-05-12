# autoresearch

This project is Assignment 3: generate 1000 meteorite images and minimize the
official FID from `evaluate_fid.py`.

The current main route is `StyleGAN2-ADA`:

- Train with `src/train_stylegan2.py`.
- Generate with `src/generate.py`.
- Evaluate final candidates with `evaluate_fid.py`.

Do not modify `evaluate_fid.py`, `meteorite/`, or the local Inception weights.

## Setup

To set up a new experiment run:

1. **Pick a run tag automatically** if one is not supplied by the user.
   Default to today's short date tag, e.g. `may12`.
2. **Create or switch to the branch**: use `autoresearch/<tag>`. If it already
   exists, switch to it; otherwise create it from `main` or the current base
   branch.
3. **Read the in-scope files**:
   - `assignment3.md` - assignment requirements.
   - `evaluate_fid.py` - official evaluator; read only, do not edit.
   - `src/train_stylegan2.py` - training wrapper.
   - `src/generate.py` - image generation wrapper.
   - `assignment3_recommendation.md` - current method rationale.
   - `meteorite/` - raw reference images; inspect only, do not modify.
4. **Initialize `results.tsv`** with only the header row if it does not already
   exist. Leave it untracked when possible.
5. **Proceed automatically** once setup is complete.

Once setup is complete, begin experimentation.

## Session Startup

Every new agent session must begin by reading these files, in this order:

1. `program.md` - long-term operating rules.
2. `run_state.json` - machine-readable current state.
3. `handoff.md` - previous agent's human-readable handoff.
4. `todo.md` - short-term task queue.
5. `plan.md` - medium-term experiment plan.
6. `results.tsv` - structured experiment history, if present.
7. Relevant recent logs only as needed, e.g. `run.log`, `generate.log`,
   `fid.log`, and `training-runs/**/metric-fid50k_full.jsonl`.

Do not start editing or running long experiments until the current best result,
last failure mode, and next recommended task are clear.

If `run_state.json` conflicts with the current git state, trust git as the
source of truth, then update `run_state.json` to match.

If a previous session left behind partial logs or an active training process,
resolve that situation before starting a new experiment.

## Synchronization Files

The autoresearch loop is designed to survive model switches and fresh sessions.
These files are the shared memory:

- `program.md`: stable rules and workflow. Change rarely.
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

- `autoresearch/logs/` - training, generation, evaluation, and command logs.
- `autoresearch/sessions/` - logs from each `opencode run` session.
- `autoresearch/tmp/` - temporary notes or scratch outputs that can be deleted.
- `training-runs/` - StyleGAN2-ADA checkpoints and internal logs.
- `generated_pictures/` - exactly the images intended for the current official
  FID evaluation.
- `evaluation_results/` - official evaluator output.

Avoid adding new root-level `run*.log`, `fid*.log`, or `gen*.log` files. Legacy
root logs may exist; do not move them while a running process or handoff still
refers to them.

## Metrics

There are two FID-like numbers in this project. Keep them separate.

### Official FID

The official score is produced only by:

```bash
uv run python evaluate_fid.py
```

It compares:

- `meteorite/` as the real reference set.
- `generated_pictures/` as the generated set.

The evaluator:

- Reads flat image files from both directories.
- Ignores `generated_grid.png`.
- Resizes each image preserving aspect ratio.
- Pads to `299x299` with a white background.
- Extracts ImageNet InceptionV3 features.
- Prints `FID: <value>`.
- Writes `evaluation_results/fid_metrics.json`.

This is the number that matters for the assignment report.

### Training Proxy FID

StyleGAN2-ADA may also log `fid50k_full` in
`training-runs/**/metric-fid50k_full.jsonl`. This is useful for choosing
checkpoints during training, but it is not the official assignment score.

Use `fid50k_full` only as a proxy. A final candidate must be generated into
`generated_pictures/` and evaluated with `evaluate_fid.py`.

## Experimentation

Each experiment runs on the single A30 GPU.

**The goal is simple: get the lowest official FID.** Change preprocessing,
resolution, StyleGAN2-ADA config, augmentation, batch size, `kimg`, snapshot
choice, truncation, and generation settings. The constraints are:

- The code must run without crashing.
- The final output must be exactly 1000 generated images for evaluation.
- `evaluate_fid.py` and `meteorite/` must remain unchanged.

**VRAM** is a soft constraint. Some increase is acceptable for meaningful FID
gains, but avoid changes that make iteration fragile on the A30.

**Simplicity criterion**: All else being equal, simpler is better. A tiny FID
gain from hacky complexity is usually not worth keeping. A tiny gain from
deleting code or simplifying preprocessing is worth keeping.

**The first run**: establish a baseline with the current training and generation
scripts before changing behavior.

## Practical Runtime Guidance

Do not assume every experiment should finish in 30 minutes. That timing came
from a different template.

The current training script defaults to `--kimg 25000`, which can be far too
long for fast autoresearch iteration. Prefer staged runs:

- Smoke test: `--kimg 1` to verify the code path.
- Quick comparison: `--kimg 200` to `--kimg 1000`.
- Stronger candidate: continue or rerun to higher `kimg` after a promising
  idea appears.

StyleGAN2-ADA snapshots and metrics are the natural checkpoints. Inspect:

```bash
tail -n 20 training-runs/**/metric-fid50k_full.jsonl
```

and choose the best promising `network-snapshot-*.pkl` for generation and
official evaluation.

Use `timeout` when appropriate, but treat timeout as a guardrail, not the
definition of a valid experiment. If a run is still improving and the idea is
promising, prefer using a planned `--kimg` or checkpoint boundary over killing
it arbitrarily.

## Output And Evaluation Commands

Typical StyleGAN2-ADA flow:

```bash
uv run python src/train_stylegan2.py --kimg 500 > run.log 2>&1
uv run python src/generate.py --network path/to/network-snapshot-000500.pkl --num 1000 > generate.log 2>&1
uv run python evaluate_fid.py > fid.log 2>&1
```

Extract useful values:

```bash
grep '"fid50k_full"' training-runs/**/metric-fid50k_full.jsonl
grep "^FID:" fid.log
cat evaluation_results/fid_metrics.json
```

If generation uses the latest checkpoint automatically, verify that it selected
the intended `network-snapshot-*.pkl` before trusting the score.

If a generation or evaluation step fails, fix the smallest obvious issue first.
Only escalate to broader debugging if the failure repeats or the root cause is
unclear.

## Logging Results

When an experiment is done, log it to `results.tsv` using tabs, not commas.

The TSV has this header:

```text
commit	official_fid	proxy_fid50k	memory_gb	status	description
```

Columns:

1. Short git commit hash, 7 chars.
2. Official FID from `evaluate_fid.py`; use `0.0000` for crashes.
3. Best relevant StyleGAN2-ADA `fid50k_full`; use `na` if unavailable.
4. Peak memory in GB if known; use `na` if not measured.
5. Status: `keep`, `discard`, or `crash`.
6. Short description of what this experiment tried.

Example:

```text
commit	official_fid	proxy_fid50k	memory_gb	status	description
a1b2c3d	52.1432	49.82	18.6	keep	baseline 256px cfnc kimg500 trunc1.0
b2c3d4e	48.9011	46.33	19.1	keep	512px preprocessing kimg500
c3d4e5f	57.0049	53.20	18.9	discard	enable geometric augmentations
d4e5f6g	0.0000	na	na	crash	batch too large OOM
```

Do not commit `results.tsv`.

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
- CUDA, PyTorch, StyleGAN2-ADA internals, or environment failures.
- Architecture design or major strategy changes.
- Confusing FID behavior, evaluator mismatch, or repeated regressions.
- Two consecutive crashes or blocked runs.

Use `deepseekv4flash` with `xhigh` or `max` for:

- Running already planned experiments.
- Implementing a clearly specified preprocessing or hyperparameter change.
- Generating images and evaluating official FID.
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
  "next_task": "Run the next planned kimg500 StyleGAN2-ADA comparison and evaluate official FID.",
  "reason": "The next task is an already specified experiment.",
  "prompt": "read program.md and continue the autoresearch loop",
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
3. Edit training/generation files or command settings.
4. Commit the code change before running the experiment.
5. Run training with redirected logs, e.g.
   `uv run python src/train_stylegan2.py --kimg 500 > run.log 2>&1`.
6. If training crashes, inspect `tail -n 80 run.log`. Fix simple bugs and
   rerun; otherwise record a crash and move on.
7. Inspect proxy metrics from `metric-fid50k_full.jsonl` when available.
8. Generate exactly 1000 images from the selected checkpoint into
   `generated_pictures/`.
9. Run `uv run python evaluate_fid.py > fid.log 2>&1`.
10. Extract `FID:` from `fid.log` and record the result in `results.tsv`.
11. If official FID improves, keep the commit and advance from it.
12. If official FID is equal or worse, discard the code change and return to
    the previous best commit, but keep the untracked `results.tsv` history.
13. Update `todo.md`, `plan.md` if strategy changed, `handoff.md`,
    `experiment_journal.md`, `run_state.json`, and
    `autoresearch_setting.json`.
14. End the current session. The external runner may start a new session with
    the selected model and reasoning variant.

Do not reset or discard unrelated user changes. Only revert your own experiment
changes when the experiment is judged worse or broken.

## End-Of-Session Handoff

Before stopping, ensure `handoff.md` includes:

- Current best commit, official FID, proxy FID, checkpoint, and generation
  settings.
- What changed in the last session.
- Commands run and where logs were written.
- Results or crash details.
- The next recommended task and why.
- Warnings for the next session.

Before stopping, ensure `experiment_journal.md` has an entry for each meaningful
attempt. Include hypothesis, changed files/settings, commands, logs,
checkpoints, official FID, proxy FID, decision, and follow-up.

Ensure `run_state.json` includes at least:

- Whether a session is active.
- Last session id and timestamp.
- Current branch.
- Best commit and best official FID.
- Last status: `not_started`, `running`, `keep`, `discard`, `crash`, or
  `blocked`.
- Consecutive crash count.
- Selected next task.

If a session is interrupted mid-run, set `last_status` to `blocked` or
`running` as appropriate, and leave enough detail in `handoff.md` for recovery.

Ensure `todo.md` has a clear top task, and `autoresearch_setting.json` has the
next model and reasoning variant.

## Notes For This Dataset

- The reference set has white-background meteorite images with varied original
  sizes and aspect ratios.
- The official evaluator already preserves aspect ratio and pads with white, so
  generated images should keep a clean white-background object-photo style.
- Do not optimize for visual prettiness alone. Modern text-to-image aesthetics
  can look good while worsening FID.
- Snapshot choice and truncation can materially affect official FID. Evaluate
  multiple promising checkpoints and truncation values before assuming the last
  checkpoint is best.

## Autonomous Operation

After the run begins, continue the experiment loop without asking whether to
keep going. Stop only if interrupted, blocked by missing resources, or the
machine cannot run the required commands.

For true unattended operation, run `scripts/autoresearch_supervisor.py` instead
of launching `scripts/autoresearch_next.py` manually. The supervisor handles the
case where an agent session exits after starting a background training process:
it waits for the recorded `training_pid` to finish, then starts the next
`opencode run` session from `autoresearch_setting.json`.
