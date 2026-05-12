# Todo

## Now

- [ ] Establish or verify the current StyleGAN2-ADA baseline with official FID.

## Next

- [ ] Compare candidate checkpoints using official `evaluate_fid.py`, not only `fid50k_full`.
- [ ] Try truncation values for the best checkpoint, e.g. `1.0`, `0.8`, `0.7`.
- [ ] Evaluate whether `256` or `512` preprocessing is worth the extra runtime.
- [ ] Record every completed run in `results.tsv`.

## Later

- [ ] Consider alternate augmentation settings after the baseline is stable.
- [ ] Summarize the best run and generation settings for the final report.
