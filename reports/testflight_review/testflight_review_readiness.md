# TestFlight / App Review Readiness

- valid: `false`
- app_id: `6786196512`
- bundle_id: `app.gitai.game`
- app_store_version: `1.0`
- app_store_state: `PREPARE_FOR_SUBMISSION`
- build_count: `0`
- internal_beta_group_count: `1`
- screenshot_count: `5`
- passed_checks: `10`
- failed_checks: `2`

## Checks

| check | status | detail |
| --- | --- | --- |
| appstore_credentials_present | pass | all keys present |
| private_key_exists | pass | /Users/ryosuke/dev/new_game/.secrets/.../AuthKey_GG8FQHQ7LD.p8 |
| jwt_generated | pass | ES256 token generated |
| app_record_found | pass | app_id=6786196512 |
| app_store_version_prepare_for_submission | pass | {"releaseType": "AFTER_APPROVAL", "state": "PREPARE_FOR_SUBMISSION", "usesIdfa": false, "version": "1.0"} |
| testflight_build_uploaded | fail | build_count=0 |
| internal_beta_group_ready | pass | group_count=1 |
| app_store_release_kit_valid | pass | passed=16 failed=0 |
| app_store_metadata_synced | pass | actions=9 |
| app_store_screenshots_generated | pass | count=5 |
| production_api_reachable | fail | dns_unresolved=api.gitai.game |
| xcode_archive_exists | pass | /Users/ryosuke/dev/new_game/build/ios/archive/gitai.xcarchive |

## Warnings

- Production API must be live before App Review. The iOS bundle currently points at GITAI_IOS_API_BASE.
- No TestFlight build is uploaded yet.

## Errors

- testflight_build_uploaded: build_count=0
- production_api_reachable: dns_unresolved=api.gitai.game
