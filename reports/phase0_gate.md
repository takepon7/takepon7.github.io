# Phase 0 Gate

Date: 2026-06-29

The initial kill-switch gate is passed for the synthetic `apple -> baseball`
fixture set.

## OpenCLIP

- Model: `open_clip:ViT-L-14:openai:fp32`
- Best practical tau in this fixture: `30` to `50`
- At tau `30`, strong-minus-weak raw delta: `0.7126`
- Text attack hard-zero: passed
- Gate: go

## SigLIP

- Model: `siglip:google/siglip-base-patch16-224:fp32`
- Best practical tau in this fixture: `100`
- At tau `30`, strong-minus-weak raw delta: `0.1204`
- At tau `100`, strong-minus-weak raw delta: `0.4534`
- Text attack hard-zero: passed
- Gate: go, but OpenCLIP currently gives a cleaner gameplay gradient on this fixture

## Interpretation

This result is enough to continue into Phase 1: deterministic scoring service,
ref_version pinning, OCR hard-zero, and percentile normalization.

It is not yet enough to claim the game is broadly fun. The next proof point is
running the same harness across more hand-made pairs and checking whether the
spread survives outside this single `apple -> baseball` case.
