# App Store Connect Check

- valid: `true`
- bundle_id: `app.gitai.game`
- bundle_found: `true`
- bundle_resource_id: `32QLDGB33V`
- app_found: `true`
- app_id: `6786196512`
- passed_checks: `7`
- failed_checks: `0`

| check | status | detail |
| --- | --- | --- |
| required_env_present | pass | all keys present |
| private_key_exists | pass | /Users/ryosuke/dev/new_game/.secrets/.../AuthKey_GG8FQHQ7LD.p8 |
| jwt_generated | pass | ES256 token generated |
| bundle_ids_endpoint_reachable | pass | matched_bundle_ids=1 |
| bundle_id_found | pass | {"id": "32QLDGB33V", "identifier": "app.gitai.game", "name": "gitai", "platform": "UNIVERSAL"} |
| apps_endpoint_reachable | pass | matched_apps=1 |
| app_record_found | pass | {"bundleId": "app.gitai.game", "id": "6786196512", "name": "gitai", "primaryLocale": "ja", "sku": "gitai-ios"} |
