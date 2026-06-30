# Approved SeedScores draft

- model_version: `heuristic-color-shape-v1`
- template_set_id: `drawing_v1`
- tau: `30`
- seed_score_refs: `1`

## Measured Quality

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30 | apple_to_baseball | true | 0.7999 | 0.1917 | 0.9585 | 0.9916 | easy | - |

## Case Scores

| pair_id | case_id | expected | raw | Cy | Cx | bucket |
| --- | --- | --- | ---: | ---: | ---: | --- |
| apple_to_baseball | apple_to_baseball_weak_bfe23091 | weak | 0.0000 | 0.0000 | 0.4806 | failed |
| apple_to_baseball | apple_to_baseball_medium_bfe23091 | medium | 0.9585 | 0.9734 | 0.0153 | fooled |
| apple_to_baseball | apple_to_baseball_strong_bfe23091 | strong | 0.9999 | 0.9999 | 0.0000 | fooled |
