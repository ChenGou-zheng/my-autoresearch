# Project

This project is Assignment 3: generate 1000 meteorite images and minimize the
official FID from `evaluate_fid.py`.

The current main route is `StyleGAN2-ADA`:

- Train with `src/train_stylegan2.py`.
- Generate with `src/generate.py`.
- Evaluate final candidates with `evaluate_fid.py`.

Do not modify `evaluate_fid.py`, `meteorite/`, or the local Inception weights.

## In-Scope Files

Read these files when setting up or resuming work:

- `assignment3.md` - assignment requirements.
- `evaluate_fid.py` - official evaluator; read only, do not edit.
- `src/train_stylegan2.py` - training wrapper.
- `src/generate.py` - image generation wrapper.
- `assignment3_recommendation.md` - current method rationale.
- `meteorite/` - raw reference images; inspect only, do not modify.

Some of these files may be absent in a stripped-down template copy. If a listed
file is missing, record that in `handoff.md` and continue with the available
project context.

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

## Constraints

Each experiment runs on the single A30 GPU.

The goal is simple: get the lowest official FID. Change preprocessing,
resolution, StyleGAN2-ADA config, augmentation, batch size, `kimg`, snapshot
choice, truncation, and generation settings.

The constraints are:

- The code must run without crashing.
- The final output must be exactly 1000 generated images for evaluation.
- `evaluate_fid.py` and `meteorite/` must remain unchanged.

VRAM is a soft constraint. Some increase is acceptable for meaningful FID
gains, but avoid changes that make iteration fragile on the A30.

## Runtime Guidance

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

## Output And Evaluation Commands

Typical StyleGAN2-ADA flow:

```bash
uv run python src/train_stylegan2.py --kimg 500 > autoresearch/logs/run.log 2>&1
uv run python src/generate.py --network path/to/network-snapshot-000500.pkl --num 1000 > autoresearch/logs/generate.log 2>&1
uv run python evaluate_fid.py > autoresearch/logs/fid.log 2>&1
```

Extract useful values:

```bash
grep '"fid50k_full"' training-runs/**/metric-fid50k_full.jsonl
grep "^FID:" autoresearch/logs/fid.log
cat evaluation_results/fid_metrics.json
```

If generation uses the latest checkpoint automatically, verify that it selected
the intended `network-snapshot-*.pkl` before trusting the score.

## Results TSV

Use this header:

```text
commit	official_fid	proxy_fid50k	memory_gb	status	description
```

Columns:

1. Short git commit hash, 7 chars.
2. Official FID from `evaluate_fid.py`; use `0.0000` for crashes.
3. Best relevant StyleGAN2-ADA `fid50k_full`; use `na` if unavailable.
4. Peak memory in GB if known; use `na` if not measured.
5. Status: `keep`, `discard`, `crash`, `blocked`, or `continue`.
6. Short description of what this experiment tried.

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
