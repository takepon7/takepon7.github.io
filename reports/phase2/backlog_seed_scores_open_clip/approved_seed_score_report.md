# Approved SeedScores draft

- model_version: `open_clip:ViT-L-14:openai:fp32`
- template_set_id: `drawing_v1`
- tau: `30`
- seed_score_refs: `1`

## Measured Quality

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| approved-seed-open-clip-vit-l-14-openai-fp32-chair-car-tau30-2026-06-30 | chair_to_car | false | 0.1029 | 0.0428 | 0.1415 | 0.1457 | hard | p90_below_impossible_floor |

## Case Scores

| pair_id | case_id | expected | raw | Cy | Cx | bucket |
| --- | --- | --- | ---: | ---: | ---: | --- |
| chair_to_car | chair_to_car_weak_backlog- | weak | 0.0181 | 0.0702 | 0.7426 | failed |
| chair_to_car | chair_to_car_medium_backlog- | medium | 0.1415 | 0.3124 | 0.5470 | failed |
| chair_to_car | chair_to_car_strong_backlog- | strong | 0.1467 | 0.3064 | 0.5210 | failed |
