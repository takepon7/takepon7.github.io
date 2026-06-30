# Public launch smoke

- valid: `true`
- passed_checks: `8`
- failed_checks: `0`
- manual_followups: `3`

| check | status | detail |
| --- | --- | --- |
| web_dist_index_exists | pass | /Users/ryosuke/dev/new_game/web/dist/index.html |
| publish_metadata_present | pass | all metadata present |
| production_api_not_localhost | pass | production bundle uses same-origin/explicit API base |
| brand_images_have_expected_sizes | pass | {"app_icon_192": {"actual": [192, 192], "expected": [192, 192], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/app-icon-192.png"}, "app_icon_512": {"actual": [512, 512], "expected": [512, 512], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/app-icon-512.png"}, "apple_touch_icon": {"actual": [180, 180], "expected": [180, 180], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/apple-touch-icon.png"}, "favicon": {"actual": [32, 32], "expected": [32, 32], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/favicon-32.png"}, "marketing_hero": {"actual": [1600, 900], "expected": [1600, 900], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/marketing-hero-16x9.png"}, "og_image": {"actual": [1200, 630], "expected": [1200, 630], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/og-image.png"}, "social_feed_square": {"actual": [1080, 1080], "expected": [1080, 1080], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/social-feed-square.png"}, "social_story_vertical": {"actual": [1080, 1920], "expected": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/social-story-vertical.png"}} |
| pwa_manifest_ready | pass | manifest includes standalone app metadata and install icons |
| launch_docs_exist | pass | marketing, asset, and deployment docs exist |
| release_readiness_valid | pass | passed=15 failed=0 |
| static_smoke_valid | pass | all static checks pass |

## Manual Follow-ups

- Set real production origins in GITAI_CORS_ORIGINS and GITAI_PUBLIC_WEB_URL before launch.
- Run an external closed playtest; the automated smoke cannot prove player fun or acquisition metrics.
- Replace heuristic playtest content with broader real-model measured pairs before a serious public campaign.
