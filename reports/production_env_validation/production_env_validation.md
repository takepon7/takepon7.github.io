# Production Env Validation

- valid: `true`
- source: `.env.production.example`
- allow_placeholders: `true`
- passed_checks: `9`
- failed_checks: `0`
- warnings: `1`

| check | status | detail |
| --- | --- | --- |
| required_keys_present | pass | all required keys present |
| public_web_url_is_https | pass | https://your-public-web-origin.example |
| public_web_url_not_placeholder | pass | https://your-public-web-origin.example |
| cors_origins_are_https | pass | https://your-public-web-origin.example |
| cors_origins_not_placeholder | pass | https://your-public-web-origin.example |
| model_and_guards_are_production_safe | pass | model=heuristic ocr=fingerprint moderation=fingerprint |
| limits_are_positive_integers | pass | {"GITAI_DAILY_LLM_SPEND_CAP": "100", "GITAI_DAILY_SUBMISSION_LIMIT": "10", "GITAI_USER_DAILY_COMMENT_LIMIT": "3"} |
| season_identity_is_set | pass | season_id=season-1 season_label=Season 1 |
| operator_token_is_strong | pass | placeholder accepted for template |

## Warnings

- GITAI_OPERATOR_TOKEN is a template placeholder; replace it with a 32+ character random value.
