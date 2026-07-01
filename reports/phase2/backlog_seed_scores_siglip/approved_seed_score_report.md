# Approved SeedScores draft

- model_version: `siglip:google/siglip-base-patch16-224:fp32`
- template_set_id: `drawing_v1`
- tau: `30`
- seed_score_refs: `1`

## Measured Quality

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-chair-car-tau30-2026-06-30 | chair_to_car | false | 0.0141 | 0.1831 | 0.1950 | 0.1971 | hard | spread_below_floor, p90_below_impossible_floor |

## Case Scores

| pair_id | case_id | expected | raw | Cy | Cx | bucket |
| --- | --- | --- | ---: | ---: | ---: | --- |
| chair_to_car | chair_to_car_weak_backlog- | weak | 0.1977 | 0.2515 | 0.2142 | confused |
| chair_to_car | chair_to_car_medium_backlog- | medium | 0.1801 | 0.2287 | 0.2124 | confused |
| chair_to_car | chair_to_car_strong_backlog- | strong | 0.1950 | 0.2454 | 0.2054 | confused |
