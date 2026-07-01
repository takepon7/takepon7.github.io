# Launch Package Audit

- valid: `true`
- latest_date: `2026-07-06`
- latest_pair_id: `apple_to_baseball`
- first_play_submission_id: `c6fd900bfef34b8d88c10c767eb2cfdf`
- passed_checks: `12`
- failed_checks: `0`
- manual_followups: `5`

| check | status | detail |
| --- | --- | --- |
| release_readiness_valid | pass | passed=15 failed=0 |
| public_launch_valid | pass | passed=13 failed=0 |
| first_play_flow_valid | pass | passed=38 failed=0 |
| static_surface_valid | pass | checks=41 |
| marketing_docs_ready | pass | all launch docs exist |
| closed_playtest_kit_ready | pass | {"missing_docs": [], "missing_tokens": []} |
| production_env_template_ready | pass | passed=9 failed=0 |
| real_model_expansion_backlog_ready | pass | real_model_pairs=6 backlog=1 |
| imagegen_assets_ready | pass | {"missing_assets": [], "missing_share_cards": [], "share_card_examples": 5} |
| policy_pages_ready | pass | privacy, terms, and safety pages exist |
| itchio_release_kit_ready | pass | {"doc": "/Users/ryosuke/dev/new_game/docs/release/itchio_release_kit.md", "ready_for_public_upload": false, "zip_path": "/Users/ryosuke/dev/new_game/releases/itchio/gitai-itchio-web-v0.1.0.zip"} |
| app_store_release_kit_ready | pass | {"doc": "/Users/ryosuke/dev/new_game/docs/release/app_store_release_plan.md", "screenshot_count": 5} |

## Manual Follow-ups

- Set production GITAI_CORS_ORIGINS and GITAI_PUBLIC_WEB_URL to the final public origin.
- Re-sync the iOS wrapper with the final production API origin and upload the first TestFlight build.
- Rebuild the itch.io ZIP with the final VITE_GITAI_API_BASE and verify the draft iframe origin.
- Run an external closed playtest with at least 20 outside players.
- Replace or expand heuristic playtest pairs with broader real-model measured pairs before a serious campaign.
