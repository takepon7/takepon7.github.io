# Approved SeedScores draft

- model_version: `siglip:google/siglip-base-patch16-224:fp32`
- template_set_id: `drawing_v1`
- tau: `30`
- seed_score_refs: `6`

## Measured Quality

| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-balloon-baseball-tau30-2026-06-30 | balloon_to_baseball | false | 0.0336 | 0.1688 | 0.1987 | 0.2024 | hard | spread_below_floor |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-book-car-tau30-2026-06-30 | book_to_car | false | 0.0060 | 0.1931 | 0.1932 | 0.1991 | hard | spread_below_floor, p90_below_impossible_floor |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-chair-car-tau30-2026-06-30 | chair_to_car | false | 0.0141 | 0.1831 | 0.1950 | 0.1971 | hard | spread_below_floor, p90_below_impossible_floor |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-mug-book-tau30-2026-06-30 | mug_to_book | false | 0.0345 | 0.1669 | 0.1782 | 0.2014 | hard | spread_below_floor |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-orange-tennis_ball-tau30-2026-06-30 | orange_to_tennis_ball | false | 0.0211 | 0.2012 | 0.2197 | 0.2223 | normal | spread_below_floor |
| approved-seed-siglip-google-siglip-base-patch16-224-fp32-tomato-baseball-tau30-2026-06-30 | tomato_to_baseball | false | 0.0387 | 0.1802 | 0.2022 | 0.2190 | normal | spread_below_floor |

## Case Scores

| pair_id | case_id | expected | raw | Cy | Cx | bucket |
| --- | --- | --- | ---: | ---: | ---: | --- |
| balloon_to_baseball | balloon_to_baseball_weak_backlog- | weak | 0.1613 | 0.2025 | 0.2033 | confused |
| balloon_to_baseball | balloon_to_baseball_medium_backlog- | medium | 0.1987 | 0.2452 | 0.1895 | confused |
| balloon_to_baseball | balloon_to_baseball_strong_backlog- | strong | 0.2033 | 0.2458 | 0.1728 | confused |
| book_to_car | book_to_car_weak_backlog- | weak | 0.1931 | 0.2387 | 0.1910 | confused |
| book_to_car | book_to_car_medium_backlog- | medium | 0.1932 | 0.2420 | 0.2014 | confused |
| book_to_car | book_to_car_strong_backlog- | strong | 0.2006 | 0.2502 | 0.1981 | confused |
| chair_to_car | chair_to_car_weak_backlog- | weak | 0.1977 | 0.2515 | 0.2142 | confused |
| chair_to_car | chair_to_car_medium_backlog- | medium | 0.1801 | 0.2287 | 0.2124 | confused |
| chair_to_car | chair_to_car_strong_backlog- | strong | 0.1950 | 0.2454 | 0.2054 | confused |
| mug_to_book | mug_to_book_weak_backlog- | weak | 0.1640 | 0.1836 | 0.1067 | confused |
| mug_to_book | mug_to_book_medium_backlog- | medium | 0.1782 | 0.2009 | 0.1129 | confused |
| mug_to_book | mug_to_book_strong_backlog- | strong | 0.2072 | 0.2337 | 0.1137 | confused |
| orange_to_tennis_ball | orange_to_tennis_ball_weak_backlog- | weak | 0.1966 | 0.2484 | 0.2085 | confused |
| orange_to_tennis_ball | orange_to_tennis_ball_medium_backlog- | medium | 0.2197 | 0.2633 | 0.1657 | confused |
| orange_to_tennis_ball | orange_to_tennis_ball_strong_backlog- | strong | 0.2230 | 0.2730 | 0.1834 | confused |
| tomato_to_baseball | tomato_to_baseball_weak_backlog- | weak | 0.2022 | 0.2381 | 0.1508 | confused |
| tomato_to_baseball | tomato_to_baseball_medium_backlog- | medium | 0.1748 | 0.2095 | 0.1660 | confused |
| tomato_to_baseball | tomato_to_baseball_strong_backlog- | strong | 0.2232 | 0.2591 | 0.1388 | confused |
