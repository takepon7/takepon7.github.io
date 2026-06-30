# First-play API smoke

- valid: `true`
- season_id: `season-1`
- today: `2026-07-06`
- pair_id: `apple_to_baseball`
- submission_id: `73e0ceeb4aca407c86a002399ba2b98a`
- score: `667`
- percentile: `0.6666666666666666`
- passed_checks: `30`
- failed_checks: `0`

| check | status | detail |
| --- | --- | --- |
| healthz | pass | status 200 |
| api_security_headers_present | pass | public API security headers are present |
| daily_archive_loads | pass | status 200 |
| daily_archive_has_entries | pass | 8 entries |
| current_daily_loads | pass | status 200 |
| premium_status_loads | pass | status 200 |
| cosmetics_load | pass | status 200 |
| default_cosmetic_available | pass | default palette is listed |
| score_ghost_loads | pass | status 200 |
| efficiency_ghost_loads | pass | status 200 |
| score_ghost_has_png | pass | score ghost image is a PNG |
| seed_score_ghost_includes_stroke_log | pass | seed score ghost exposes replayable strokes |
| seed_efficiency_ghost_includes_stroke_log | pass | seed efficiency ghost exposes replayable strokes |
| pre_submit_score_is_deterministic | pass | status 200 |
| submission_accepts_replayable_drawing | pass | status 200 |
| score_leaderboard_loads_after_submit | pass | status 200 |
| friend_leaderboard_loads_after_submit | pass | status 200 |
| friend_ladder_contains_player | pass | ['73e0ceeb4aca407c86a002399ba2b98a'] |
| friend_ghost_loads_after_submit | pass | status 200 |
| friend_ghost_includes_stroke_log | pass | friend ghost exposes replayable strokes |
| share_card_generates_png | pass | status 200 |
| funny_vote_accepts_viewer | pass | status 200 |
| funny_ladder_loads | pass | status 200 |
| appraiser_comment_falls_back_safely | pass | status 200 |
| appraiser_comment_has_line | pass | fallback_unavailable |
| premium_code_redeems | pass | status 200 |
| premium_status_updates | pass | status 200 |
| pair_proposal_accepts_current_labels | pass | status 200 |
| pair_proposal_is_reviewable | pass | candidate |
| archived_daily_submissions_accept_replayable_drawings | pass | 8 archived DailyPuzzle submissions accepted |
