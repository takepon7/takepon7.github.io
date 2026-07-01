# App Store Connect Check

- valid: `false`
- bundle_id: `app.gitai.game`
- bundle_found: `false`
- bundle_resource_id: ``
- app_found: `false`
- app_id: ``
- passed_checks: `5`
- failed_checks: `2`

| check | status | detail |
| --- | --- | --- |
| required_env_present | pass | all keys present |
| private_key_exists | pass | /Users/ryosuke/dev/new_game/.secrets/.../AuthKey_GG8FQHQ7LD.p8 |
| jwt_generated | pass | ES256 token generated |
| bundle_ids_endpoint_reachable | pass | matched_bundle_ids=0 |
| bundle_id_found | fail | No bundle ID found for app.gitai.game |
| apps_endpoint_reachable | pass | matched_apps=0 |
| app_record_found | fail | No App Store app record found for bundle_id=app.gitai.game |

## Errors

- bundle_id_found: No bundle ID found for app.gitai.game
- app_record_found: No App Store app record found for bundle_id=app.gitai.game
