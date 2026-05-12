# Plan

## Objective

Minimize the official FID produced by `evaluate_fid.py` for 1000 generated
meteorite images in `generated_pictures/`.

## Current Strategy

Use `StyleGAN2-ADA` as the main route because the dataset is a narrow
white-background object domain and the assignment evaluates distributional
similarity with FID.

## Experiment Roadmap

1. Verify the baseline pipeline end to end:
   train, generate exactly 1000 images, run official FID, record the result.
2. Use `fid50k_full` only to shortlist snapshots.
3. For each promising checkpoint, run official FID after generation.
4. Sweep simple generation settings such as truncation before changing model
   internals.
5. If baseline quality plateaus, compare preprocessing resolution and padding
   choices.
6. Only then try more invasive StyleGAN2-ADA changes such as config,
   augmentation, gamma, or batch size.

## Decision Rules

- Keep changes that improve official FID and do not add fragile complexity.
- Discard changes that only improve proxy FID but worsen official FID.
- Prefer simple preprocessing and generation changes before architecture edits.
- Upgrade the next session to `deepseekv4pro` with `max` reasoning after
  repeated crashes, confusing evaluator behavior, or major strategy decisions.
