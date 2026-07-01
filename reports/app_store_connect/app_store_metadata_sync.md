# App Store Metadata Sync

- valid: `true`
- app_id: `6786196512`
- app_info_id: `33840f48-7299-4a95-937d-60e004bc2848`
- app_store_version_id: `64d20a1f-231c-4ec4-832a-fa387f8f31f2`
- actions: `7`
- passed_checks: `5`
- failed_checks: `0`

## Checks

| check | status | detail |
| --- | --- | --- |
| app_record_found | pass | id=6786196512 |
| app_info_found | pass | id=33840f48-7299-4a95-937d-60e004bc2848 |
| app_store_version_found | pass | id=64d20a1f-231c-4ec4-832a-fa387f8f31f2 |
| localizations_found | pass | info=4e36cac6-f1f7-4d3e-9d81-43796db0e69e version=b2dad75b-5c13-49f5-9e32-e74bc19378c6 |
| url_metadata_synced | pass | skipped until final production URLs are set |

## Actions

| target | status | detail |
| --- | --- | --- |
| appInfoLocalization | updated | name,subtitle |
| appStoreVersionLocalization | bulk_failed | HTTP 409 STATE_ERROR The request cannot be fulfilled because of the state of another resource. Attribute 'whatsNew' cannot be edited at this time |
| appStoreVersionLocalization.description | updated | description |
| appStoreVersionLocalization.keywords | updated | keywords |
| appStoreVersionLocalization.promotionalText | updated | promotionalText |
| appStoreVersionLocalization.whatsNew | skipped | HTTP 409 STATE_ERROR The request cannot be fulfilled because of the state of another resource. Attribute 'whatsNew' cannot be edited at this time |
| appStoreVersion | updated | copyright,releaseType,usesIdfa |
