# Public launch smoke

- valid: `true`
- passed_checks: `13`
- failed_checks: `0`
- manual_followups: `3`

| check | status | detail |
| --- | --- | --- |
| web_dist_index_exists | pass | /Users/ryosuke/dev/new_game/web/dist/index.html |
| publish_metadata_present | pass | all metadata present |
| production_api_not_localhost | pass | production bundle uses same-origin/explicit API base |
| playtest_feedback_surface_present | pass | result screen includes feedback submission controls |
| brand_images_have_expected_sizes | pass | {"app_icon_192": {"actual": [192, 192], "expected": [192, 192], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/app-icon-192.png"}, "app_icon_512": {"actual": [512, 512], "expected": [512, 512], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/app-icon-512.png"}, "apple_touch_icon": {"actual": [180, 180], "expected": [180, 180], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/apple-touch-icon.png"}, "favicon": {"actual": [32, 32], "expected": [32, 32], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/favicon-32.png"}, "marketing_hero": {"actual": [1600, 900], "expected": [1600, 900], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/marketing-hero-16x9.png"}, "og_image": {"actual": [1200, 630], "expected": [1200, 630], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/og-image.png"}, "social_feed_square": {"actual": [1080, 1080], "expected": [1080, 1080], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/social-feed-square.png"}, "social_story_vertical": {"actual": [1080, 1920], "expected": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/social-story-vertical.png"}} |
| marketing_share_card_examples_ready | pass | {"count": 5, "images": [{"actual": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/share-cards/share-card-example-2026-06-29-apple_to_baseball.png"}, {"actual": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/share-cards/share-card-example-2026-06-30-balloon_to_baseball.png"}, {"actual": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/share-cards/share-card-example-2026-07-01-orange_to_tennis_ball.png"}, {"actual": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/share-cards/share-card-example-2026-07-02-tomato_to_baseball.png"}, {"actual": [1080, 1920], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/brand/share-cards/share-card-example-2026-07-03-mug_to_book.png"}], "manifest": "/Users/ryosuke/dev/new_game/web/dist/brand/share-card-examples.json", "ok": true, "pair_count": 5} |
| pwa_manifest_ready | pass | manifest includes standalone app metadata and install icons |
| public_policy_pages_ready | pass | {"linked_from_app": ["/privacy.html", "/terms.html", "/safety.html", "/support.html"], "pages": {"privacy": {"missing": [], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/privacy.html"}, "safety": {"missing": [], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/safety.html"}, "support": {"missing": [], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/support.html"}, "terms": {"missing": [], "ok": true, "path": "/Users/ryosuke/dev/new_game/web/dist/terms.html"}}} |
| same_origin_web_serving_ready | pass | {"api_pair_id": "apple_to_baseball", "api_status": 200, "app_status": 200, "asset_status": 200, "brand_status": 200, "cache_control": {"api": "no-store", "app": "no-cache", "asset": "public, max-age=31536000, immutable", "brand": "public, max-age=86400"}, "csp": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'", "ok": true, "privacy_status": 200, "support_status": 200} |
| container_deploy_files_ready | pass | {"dockerfile": "/Users/ryosuke/dev/new_game/Dockerfile", "dockerignore": "/Users/ryosuke/dev/new_game/.dockerignore", "missing_dockerfile_tokens": [], "missing_dockerignore_tokens": [], "ok": true} |
| launch_docs_exist | pass | marketing, asset, copy, press, and deployment docs exist |
| release_readiness_valid | pass | passed=15 failed=0 |
| static_smoke_valid | pass | all static checks pass |

## Manual Follow-ups

- Point DNS and hosting for gitai.game and api.gitai.game before launch.
- Run an external closed playtest; in-app feedback is wired, but automated smoke cannot prove player fun or acquisition metrics.
- Replace heuristic playtest content with broader real-model measured pairs before a serious public campaign.
