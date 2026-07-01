# App Store Connect Check

- valid: `false`
- bundle_id: `app.gitai.game`
- bundle_found: `true`
- bundle_resource_id: `32QLDGB33V`
- app_found: `false`
- app_id: ``
- passed_checks: `6`
- failed_checks: `1`

| check | status | detail |
| --- | --- | --- |
| required_env_present | pass | all keys present |
| private_key_exists | pass | /Users/ryosuke/dev/new_game/.secrets/.../AuthKey_GG8FQHQ7LD.p8 |
| jwt_generated | pass | ES256 token generated |
| bundle_ids_endpoint_reachable | pass | matched_bundle_ids=1 |
| bundle_id_found | pass | {"id": "32QLDGB33V", "identifier": "app.gitai.game", "name": "gitai", "platform": "UNIVERSAL"} |
| apps_endpoint_reachable | pass | matched_apps=0 |
| app_record_found | fail | No App Store app record found for bundle_id=app.gitai.game |

## Errors

- app_record_found: No App Store app record found for bundle_id=app.gitai.game
