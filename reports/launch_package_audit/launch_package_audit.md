# Launch Package Audit

- valid: `true`
- latest_date: `2026-07-06`
- latest_pair_id: `apple_to_baseball`
- first_play_submission_id: `d09eebf1cd0d47deb5586ee5f7f1a2ba`
- passed_checks: `9`
- failed_checks: `0`
- manual_followups: `3`

| check | status | detail |
| --- | --- | --- |
| release_readiness_valid | pass | passed=15 failed=0 |
| public_launch_valid | pass | passed=13 failed=0 |
| first_play_flow_valid | pass | passed=38 failed=0 |
| static_surface_valid | pass | checks=41 |
| marketing_docs_ready | pass | all launch docs exist |
| closed_playtest_kit_ready | pass | {"missing_docs": [], "missing_tokens": []} |
| production_env_template_ready | pass | passed=9 failed=0 |
| imagegen_assets_ready | pass | {"missing_assets": [], "missing_share_cards": [], "share_card_examples": 5} |
| policy_pages_ready | pass | privacy, terms, and safety pages exist |

## Manual Follow-ups

- Set production GITAI_CORS_ORIGINS and GITAI_PUBLIC_WEB_URL to the final public origin.
- Run an external closed playtest with at least 20 outside players.
- Replace or expand heuristic playtest pairs with broader real-model measured pairs before a serious campaign.
