# Handoff

## Current Best

- Commit: `199834c` (add --resume support, reduce default kimg to 5000)
- Official FID: **68.45** (snapshot-001400, trunc=1.0)
- Proxy fid50k_full: 52.17 (snapshot-001400)
- Checkpoint: `training-runs/00000-meteorite256-mirror-auto1-kimg25000-cfnc/network-snapshot-001400.pkl`
- Generation settings: trunc=1.0, seeds 0-999, 256px

## Last Session

- Ran checkpoint comparison across snapshot-000600, 001200, 001400
- Swept truncation values (0.7, 0.8, 0.9, 1.0) on snapshot-001400
- Best FID: 68.45 at snapshot-001400 trunc=1.0
- Started, then manually stopped, resumed training:
  `src/train_stylegan2.py --kimg 2000 --resume <snapshot-001400>.pkl --skip-preprocess`
  - Run dir: `training-runs/00001-meteorite256-mirror-auto1-kimg2000-cfnc-resumecustom/`
  - PID: 963395, stopped by user request
  - Log: `autoresearch/logs/legacy/run_resume.log`
  - First FID eval showed proxy FID 52.29 at tick 0 (correct resume)
- Archived root-level run/fid/gen logs to `autoresearch/logs/legacy/`
- Added `experiment_journal.md` for detailed attempt tracking

## Next Recommended Task

- Do not wait for the killed resumed training process; it is stopped.
- Use shorter, checkpoint-bounded continuation runs before committing to long
  training, e.g. continue 200 kimg from snapshot-001400 and evaluate official
  FID.
- Keep writing detailed attempts to `experiment_journal.md`.

## Warnings

- Do not modify `evaluate_fid.py`, `meteorite/`, or Inception weights
- No background training should be running now
- Legacy root logs have been moved to `autoresearch/logs/legacy/`
- The old training process `00000-*` was killed — checkpoints there remain valid
- results.tsv has all completed experiments recorded
