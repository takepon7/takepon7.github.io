# Release readiness smoke

- valid: `true`
- season_id: `season-1`
- latest_date: `2026-07-06`
- latest_pair_id: `apple_to_baseball`
- daily_count: `8`
- seed_ghost_count: `16`
- passed_checks: `15`
- failed_checks: `0`

## Checks

| check | status | detail |
| --- | --- | --- |
| canonical_files_exist | pass | all canonical files exist |
| pairs_are_available | pass | 7 pairs |
| seed_scores_are_available | pass | 10 seed score refs |
| daily_puzzles_are_available | pass | 8 daily puzzles |
| seed_ghosts_are_available | pass | 16 seed ghosts |
| daily_dates_are_unique | pass | DailyPuzzle dates are unique |
| daily_entries_reference_known_pairs_and_refs | pass | all DailyPuzzle entries resolve |
| seed_ghosts_cover_daily_entries | pass | seed ghosts cover every day |
| release_candidate_validation_passes | pass | canonical bundle validates against release candidate checks |
| rollback_dry_run_ready | pass | rollback dry-run is valid and did not mutate canonical data |
| web_dist_assets_exist | pass | web dist assets resolve |
| phase3_static_smoke_passes | pass | all static checks pass |
| api_smoke_passes_latest_daily | pass | API smoke passed for 2026-07-06 |
| first_play_api_flow_passes | pass | first player flow passed |
| phase5_layer2_budget_gate_passes | pass | daily_spend=5 cap=5 degraded=true |

## API Smoke

- today: `2026-07-06`
- daily_puzzle: `apple_to_baseball`
- score_deterministic: `true`

## First Play

- valid: `true`
- submission_id: `f44eeec3bd214ef4970f463e7d6cfaa5`
- score: `667`

## Phase 5 Budget

- gate_passed: `true`
- daily_spend: `5` / `5`
- degraded_gracefully: `true`
