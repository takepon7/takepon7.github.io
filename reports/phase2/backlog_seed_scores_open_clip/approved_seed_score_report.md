# Approved SeedScores draft

- model_version: `open_clip:ViT-L-14:openai:fp32`
- template_set_id: `drawing_v1`
- tau: `30`
- seed_score_refs: `6`

## Measured Quality

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| approved-seed-open-clip-vit-l-14-openai-fp32-balloon-baseball-tau30-2026-06-30 | balloon_to_baseball | true | 0.5106 | 0.0555 | 0.2260 | 0.5661 | normal | - |
| approved-seed-open-clip-vit-l-14-openai-fp32-book-car-tau30-2026-06-30 | book_to_car | true | 0.4556 | 0.1455 | 0.5862 | 0.6011 | easy | - |
| approved-seed-open-clip-vit-l-14-openai-fp32-chair-car-tau30-2026-06-30 | chair_to_car | false | 0.1029 | 0.0428 | 0.1415 | 0.1457 | hard | p90_below_impossible_floor |
| approved-seed-open-clip-vit-l-14-openai-fp32-mug-book-tau30-2026-06-30 | mug_to_book | true | 0.1322 | 0.1021 | 0.1453 | 0.2343 | hard | - |
| approved-seed-open-clip-vit-l-14-openai-fp32-orange-tennis_ball-tau30-2026-06-30 | orange_to_tennis_ball | true | 0.6056 | 0.1840 | 0.6858 | 0.7896 | easy | - |
| approved-seed-open-clip-vit-l-14-openai-fp32-tomato-baseball-tau30-2026-06-30 | tomato_to_baseball | true | 0.4056 | 0.1020 | 0.4389 | 0.5076 | normal | - |

## Case Scores

| pair_id | case_id | expected | raw | Cy | Cx | bucket |
| --- | --- | --- | ---: | ---: | ---: | --- |
| balloon_to_baseball | balloon_to_baseball_weak_backlog- | weak | 0.0128 | 0.0511 | 0.7488 | failed |
| balloon_to_baseball | balloon_to_baseball_medium_backlog- | medium | 0.2260 | 0.3164 | 0.2856 | confused |
| balloon_to_baseball | balloon_to_baseball_strong_backlog- | strong | 0.6511 | 0.7076 | 0.0799 | fooled |
| book_to_car | book_to_car_weak_backlog- | weak | 0.0353 | 0.1008 | 0.6497 | failed |
| book_to_car | book_to_car_medium_backlog- | medium | 0.5862 | 0.6440 | 0.0898 | fooled |
| book_to_car | book_to_car_strong_backlog- | strong | 0.6048 | 0.6672 | 0.0936 | fooled |
| chair_to_car | chair_to_car_weak_backlog- | weak | 0.0181 | 0.0702 | 0.7426 | failed |
| chair_to_car | chair_to_car_medium_backlog- | medium | 0.1415 | 0.3124 | 0.5470 | failed |
| chair_to_car | chair_to_car_strong_backlog- | strong | 0.1467 | 0.3064 | 0.5210 | failed |
| mug_to_book | mug_to_book_weak_backlog- | weak | 0.1453 | 0.2033 | 0.2853 | confused |
| mug_to_book | mug_to_book_medium_backlog- | medium | 0.0914 | 0.1820 | 0.4981 | failed |
| mug_to_book | mug_to_book_strong_backlog- | strong | 0.2566 | 0.4096 | 0.3736 | confused |
| orange_to_tennis_ball | orange_to_tennis_ball_weak_backlog- | weak | 0.0585 | 0.1398 | 0.5811 | failed |
| orange_to_tennis_ball | orange_to_tennis_ball_medium_backlog- | medium | 0.6858 | 0.7604 | 0.0981 | fooled |
| orange_to_tennis_ball | orange_to_tennis_ball_strong_backlog- | strong | 0.8155 | 0.8531 | 0.0441 | fooled |
| tomato_to_baseball | tomato_to_baseball_weak_backlog- | weak | 0.0177 | 0.0300 | 0.4096 | failed |
| tomato_to_baseball | tomato_to_baseball_medium_backlog- | medium | 0.4389 | 0.4929 | 0.1095 | failed |
| tomato_to_baseball | tomato_to_baseball_strong_backlog- | strong | 0.5247 | 0.5603 | 0.0634 | fooled |
