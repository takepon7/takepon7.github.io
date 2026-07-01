# itch.io Web Release Kit

- ready_for_public_upload: `false`
- passed_checks: `14`
- failed_checks: `1`
- zip: `/Users/ryosuke/dev/new_game/releases/itchio/gitai-itchio-web-v0.1.0.zip`
- zip_sha256: `04d12b180989d294479032ce4fa07e24eb630ac91f6804bbe0eebb66d6dae44d`
- zip_bytes: `19878294`
- file_count: `26`
- api_base: `not set`

## Upload

1. Create or open an itch.io draft project.
2. Set project kind to HTML/browser playable.
3. Upload the zip above and mark it as playable in browser.
4. Keep the page restricted until the live API origin and CORS origin are verified.
5. After the iframe loads, submit one drawing, open one share card, and record feedback once.

## Page Metadata

- title: `gitai`
- short_text: 絵でAI鑑定士をだます、毎日更新の擬態ドローイングゲーム。
- release_status: `prototype / public playtest`
- pricing: `Free or pay what you want`
- tags: drawing, puzzle, web, async, leaderboard
- viewport: `1280x720 or responsive fullscreen`

## Description

りんごを野球ボールに、椅子を車に。gitai は、与えられた素体を別のモノに見えるよう描き足して、AI鑑定士をどこまでだませるか競うWebゲームです。毎日の課題、ランキング、ゴーストリプレイ、シェアカードで短く遊べます。

## Checks

| check | status | detail |
| --- | --- | --- |
| root_index.html_exists | pass | index.html |
| root_privacy.html_exists | pass | privacy.html |
| root_terms.html_exists | pass | terms.html |
| root_safety.html_exists | pass | safety.html |
| root_site.webmanifest_exists | pass | site.webmanifest |
| assets_directory_exists | pass | assets/* |
| brand_app-icon-192_exists | pass | brand/app-icon-192.png |
| brand_app-icon-512_exists | pass | brand/app-icon-512.png |
| brand_favicon-32_exists | pass | brand/favicon-32.png |
| brand_og-image_exists | pass | brand/og-image.png |
| brand_social-feed-square_exists | pass | brand/social-feed-square.png |
| brand_social-story-vertical_exists | pass | brand/social-story-vertical.png |
| bundle_has_no_localhost_api | pass | no localhost/127.0.0.1 |
| external_api_base_configured_for_itchio | fail | set --api-base to the deployed API origin before public upload |
| zip_root_will_contain_index | pass | index.html at zip root |

## Manual Follow-ups

- Upload the zip to an itch.io draft page as an HTML5/browser-playable file.
- After itch.io assigns the final game frame origin, add that origin to GITAI_CORS_ORIGINS.
- Set GITAI_PUBLIC_WEB_URL to the public itch.io project URL before public promotion.

## Official References

- https://itch.io/docs/creators/html5
- https://itch.io/docs/butler/
