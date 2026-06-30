# Real Model Pair Coverage

- valid: `true`
- pair_count: `7`
- seed_score_count: `15`
- daily_count: `8`
- real_model_pair_count: `6`
- heuristic_only_pair_count: `1`
- daily_real_model_ref_count: `0`
- daily_real_model_alternative_count: `7`

## Real-Model Covered Pairs

- `apple_to_baseball`
- `balloon_to_baseball`
- `book_to_car`
- `mug_to_book`
- `orange_to_tennis_ball`
- `tomato_to_baseball`

## Expansion Backlog

| pair_id | base | target | recommended_models |
| --- | --- | --- | --- |
| `chair_to_car` | chair | car | open_clip:ViT-L-14:openai:fp32, siglip:google/siglip-base-patch16-224:fp32 |

## Recommended Next Actions

- Run SeedAsset scoring for each expansion_backlog pair with open_clip and/or siglip.
- Promote accepted real-model SeedScores into data/scoring/seed_scores.json.
- Plan future DailyPuzzle entries against real-model ref_versions before a serious public campaign.
