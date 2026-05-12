# Experiment Journal

This file is the detailed narrative record of autoresearch attempts. Keep
`results.tsv` compact and append-only; use this file for reasoning, commands,
caveats, and follow-up notes behind each result.

## Entry Template

### YYYY-MM-DD HH:MM - short title

- Status:
- Hypothesis:
- Files/settings changed:
- Commands:
- Logs:
- Checkpoints:
- Official FID:
- Proxy fid50k_full:
- Decision:
- Follow-up:

## 2026-05-12 - Baseline and Checkpoint/Truncation Sweep

- Status: keep
- Hypothesis: Existing StyleGAN2-ADA 256px cfnc training may already have a
  useful checkpoint; official FID should be evaluated across snapshots and
  truncation values instead of trusting proxy `fid50k_full` alone.
- Files/settings changed:
  - Commit `6106613`: baseline 256px cfnc setup.
  - Commit `199834c`: added resume support and reduced default kimg to 5000.
- Commands:
  - Generated 1000 images from snapshots 000600, 001200, and 001400.
  - Evaluated each generated set with `evaluate_fid.py`.
  - Swept truncation values 0.7, 0.8, 0.9, and 1.0 for snapshot 001400.
- Logs:
  - Archived root logs under `autoresearch/logs/legacy/`.
- Checkpoints:
  - `training-runs/00000-meteorite256-mirror-auto1-kimg25000-cfnc/network-snapshot-000600.pkl`
  - `training-runs/00000-meteorite256-mirror-auto1-kimg25000-cfnc/network-snapshot-001200.pkl`
  - `training-runs/00000-meteorite256-mirror-auto1-kimg25000-cfnc/network-snapshot-001400.pkl`
- Official FID:
  - snapshot-000600 trunc=1.0: 93.9487
  - snapshot-001200 trunc=1.0: 74.2177
  - snapshot-001400 trunc=1.0: 68.4459
  - snapshot-001400 trunc=0.9: 68.6895
  - snapshot-001400 trunc=0.8: 72.5195
  - snapshot-001400 trunc=0.7: 80.7609
- Proxy fid50k_full:
  - snapshot-000600: 73.67
  - snapshot-001200: 52.55
  - snapshot-001400: 52.17
- Decision: Best official FID so far is 68.4459 from snapshot-001400 with
  trunc=1.0. Truncation did not improve official FID.
- Follow-up: Try more training from snapshot-001400, but use shorter bounded
  runs so the loop can evaluate checkpoints sooner.

## 2026-05-12 - Resumed Training From Snapshot 001400

- Status: stopped
- Hypothesis: Continuing training from snapshot-001400 may improve official FID
  beyond 68.4459.
- Files/settings changed:
  - Used resume support from commit `199834c`.
- Commands:
  - `src/train_stylegan2.py --kimg 2000 --resume <snapshot-001400>.pkl --skip-preprocess`
- Logs:
  - `autoresearch/logs/legacy/run_resume.log`
  - `training-runs/00001-meteorite256-mirror-auto1-kimg2000-cfnc-resumecustom/log.txt`
  - `training-runs/00001-meteorite256-mirror-auto1-kimg2000-cfnc-resumecustom/metric-fid50k_full.jsonl`
- Checkpoints:
  - `training-runs/00001-meteorite256-mirror-auto1-kimg2000-cfnc-resumecustom/network-snapshot-000000.pkl`
- Official FID: not evaluated for resumed checkpoints.
- Proxy fid50k_full:
  - tick 0 / snapshot-000000: 52.2875
- Decision: User requested stopping the long background run. PID 963395 was
  terminated after roughly 1h39m elapsed; no later checkpoint was evaluated.
- Follow-up: Prefer shorter continuation windows or checkpoint-bound runs, e.g.
  continue 200 kimg, evaluate, then decide whether to proceed.

## 2026-05-12 - Centered Preprocessing + Fresh 256px Training

- Status: running (PID 969003)
- Hypothesis: Centering meteorites in the raw images before resize+pad removes
  positional variance from the data, letting the generator focus on appearance.
- Files/settings changed:
  - `src/train_stylegan2.py`: Added `detect_bbox()` to find the meteorite's
    bounding box (non-white pixels), crops to it with 5% margin, then does the
    usual resize+pad. Added `--center` flag, dynamic data-dir naming
    (`meteorite{resolution}{-centered}/`).
- Commands:
  - `uv run python src/train_stylegan2.py --resolution 256 --center --kimg 3000`
- Logs:
  - `autoresearch/logs/train_centered256.log`
- Checkpoints:
  - `training-runs/00002-*/network-snapshot-*.pkl` (when available)
- Proxy fid50k_full:
  - tick 0: 383.51 (random init, expected)
  - tick 1-2: ~52-53 range
- Decision: TBD - wait for checkpoints at kimg ~600-1400 to compare with
  baseline (snapshot-000600: 73.67 proxy, snapshot-001400: 52.17 proxy).
- Follow-up: If proxy FID at kimg 600 is better than 73.67, centering helps.
  Then evaluate official FID and consider 512px run.
