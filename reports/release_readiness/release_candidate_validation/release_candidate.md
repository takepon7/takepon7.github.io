# Release candidate validation

- valid: `true`
- season_id: `season-1`
- pair_count: `7`
- seed_score_count: `15`
- daily_count: `8`
- planned_count: `1`
- seed_ghost_count: `16`
- preview_today: `2026-07-06`

## Checks

| check | status | detail |
| --- | --- | --- |
| promotion_has_no_errors | pass | 0 promotion errors |
| daily_plan_has_no_errors | pass | 0 DailyPuzzle plan errors |
| daily_plan_has_required_new_entries | pass | 1 planned entries, expected at least 0 |
| daily_dates_are_unique | pass | DailyPuzzle dates must be unique |
| daily_entries_reference_known_pairs_and_refs | pass | all DailyPuzzle entries resolve |
| seed_ghosts_cover_daily_entries | pass | seed ghosts valid |

## Warnings

- promotion is a preview; validation does not apply canonical scoring files
- DailyPuzzle plan is a preview; validation does not apply canonical DailyPuzzle files

## API Preview

```bash
GITAI_PAIRS_PATH=/Users/ryosuke/dev/new_game/data/scoring/pairs.json \
GITAI_SEED_SCORES_PATH=/Users/ryosuke/dev/new_game/data/scoring/seed_scores.json \
GITAI_DAILY_PUZZLES_PATH=/Users/ryosuke/dev/new_game/data/puzzle/daily_puzzles.json \
GITAI_SEED_GHOSTS=/Users/ryosuke/dev/new_game/data/competition/seed_ghosts.json \
GITAI_SEASON_ID=season-1 \
GITAI_TODAY=2026-07-06 \
npm run dev:api:fast
```
