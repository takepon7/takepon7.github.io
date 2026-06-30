# Phase 2 Puzzle Pool

- catalog_objects: `12`
- plausible_candidate_pairs: `132`
- measured_seed_refs: `3`
- accepted_measured_refs: `3`

## Measured Qualities

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| phase0-heuristic-tau30-2026-06-29 | apple_to_baseball | true | 0.8000 | 0.0272 | 0.1362 | 0.8272 | hard | - |
| phase0-open-clip-tau30-2026-06-29 | apple_to_baseball | true | 0.5701 | 0.0349 | 0.1069 | 0.6050 | hard | - |
| phase0-siglip-tau30-2026-06-29 | apple_to_baseball | true | 0.0964 | 0.1308 | 0.1468 | 0.2272 | hard | - |

## Gate

Not complete. The funnel is implemented, but the Phase 2 gate requires dozens of measured pairs. This run only has the Phase 0 `apple -> baseball` seed distribution.
