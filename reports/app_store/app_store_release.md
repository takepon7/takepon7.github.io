# App Store Release Audit

- valid: `true`
- passed_checks: `15`
- failed_checks: `0`
- screenshot_count: `5`

| check | status | detail |
| --- | --- | --- |
| release_plan_exists | pass | /Users/ryosuke/dev/new_game/docs/release/app_store_release_plan.md |
| metadata_ja_exists | pass | /Users/ryosuke/dev/new_game/docs/release/app_store_metadata_ja.md |
| connect_api_notes_exists | pass | /Users/ryosuke/dev/new_game/docs/release/app_store_connect_api.md |
| env_template_exists | pass | /Users/ryosuke/dev/new_game/.env.appstore.example |
| metadata_required_fields_ready | pass | all metadata sections present |
| appstore_env_template_ready | pass | all App Store env keys present |
| store_visual_assets_ready | pass | icon source, og image, and hero are present |
| ios_wrapper_files_ready | pass | Capacitor iOS project exists |
| capacitor_config_ready | pass | appId=app.gitai.game webDir=web/dist |
| ios_bundle_api_base_ready | pass | iOS bundle has non-local API configuration hook |
| ios_native_assets_ready | pass | {"app_icon": [1024, 1024], "splash": [2732, 2732]} |
| iphone_6_9_screenshots_ready | pass | {"bad": [], "count": 5, "expected_size": [1290, 2796]} |
| web_launch_package_valid | pass | passed=12 failed=0 |
| app_store_connect_record_ready | pass | {"app_id": "6786196512", "bundle_id": "app.gitai.game", "bundle_resource_id": "32QLDGB33V"} |
| app_store_text_metadata_synced | pass | {"actions": 7, "missing": []} |

## Screenshots

- `/Users/ryosuke/dev/new_game/reports/app_store/screenshots/generated/iphone-6.9/01.png`: `1290x2796`
- `/Users/ryosuke/dev/new_game/reports/app_store/screenshots/generated/iphone-6.9/02.png`: `1290x2796`
- `/Users/ryosuke/dev/new_game/reports/app_store/screenshots/generated/iphone-6.9/03.png`: `1290x2796`
- `/Users/ryosuke/dev/new_game/reports/app_store/screenshots/generated/iphone-6.9/04.png`: `1290x2796`
- `/Users/ryosuke/dev/new_game/reports/app_store/screenshots/generated/iphone-6.9/05.png`: `1290x2796`

## Manual Follow-ups

- Re-sync the iOS wrapper with the final production API origin.
- Sync App Store URL metadata after final production URLs replace example.com placeholders.
- Upload an archive build and run TestFlight first-play QA.
- Attach generated screenshots and submit with manual release.
