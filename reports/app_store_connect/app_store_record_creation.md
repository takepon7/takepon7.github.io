# App Store Record Creation

- valid: `false`
- bundle_id: `app.gitai.game`
- bundle_found: `true`
- bundle_resource_id: `32QLDGB33V`
- app_found: `false`
- app_id: ``
- app_name: ``
- app_sku: ``
- passed_checks: `4`
- failed_checks: `1`

| check | status | detail |
| --- | --- | --- |
| required_env_present | pass | all keys present |
| private_key_exists | pass | private key exists |
| jwt_generated | pass | ES256 token generated |
| bundle_id_ready | pass | created id=32QLDGB33V |
| app_record_ready | fail | HTTP 403 FORBIDDEN_ERROR The given operation is not allowed The resource 'apps' does not allow 'CREATE'. Allowed operations are: GET_COLLECTION, GET_INSTANCE, UPDATE |

## Errors

- app_record_ready: HTTP 403 FORBIDDEN_ERROR The given operation is not allowed The resource 'apps' does not allow 'CREATE'. Allowed operations are: GET_COLLECTION, GET_INSTANCE, UPDATE
