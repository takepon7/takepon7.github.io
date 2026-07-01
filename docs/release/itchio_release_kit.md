# itch.io Release Kit

This kit packages `web/dist` as a browser-playable itch.io HTML5 upload.

## Release Shape

- itch.io hosts the static web app ZIP.
- The game API runs on a separate production origin.
- The web build must be compiled with `VITE_GITAI_API_BASE` pointing at that API origin.
- The API must allow the final itch.io frame origin in `GITAI_CORS_ORIGINS`.

## Build

```bash
VITE_GITAI_API_BASE=https://your-api.example.com npm run build
PYTHONPATH=src .venv310/bin/python tools/build_itchio_release_kit.py \
  --api-base https://your-api.example.com
```

This writes:

- `releases/itchio/gitai-itchio-web-v0.1.0.zip`
- `releases/itchio/gitai-itchio-web-v0.1.0.manifest.json`
- `reports/itchio_release/itchio_release.md`
- `reports/itchio_release/itchio_release.json`

For a fully repeatable build from the tool:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_itchio_release_kit.py \
  --build \
  --api-base https://your-api.example.com
```

## itch.io Upload Settings

- Project title: `gitai`
- Kind: HTML / browser playable
- Upload: `gitai-itchio-web-v0.1.0.zip`
- Pricing: Free or pay what you want
- Visibility: Draft or restricted until API and CORS are verified
- Viewport: responsive fullscreen, or 1280x720 if a fixed frame is required
- Tags: `drawing`, `puzzle`, `web`, `async`, `leaderboard`

## Store Copy

Short text:

```text
絵でAI鑑定士をだます、毎日更新の擬態ドローイングゲーム。
```

Description:

```text
りんごを野球ボールに、椅子を車に。gitai は、与えられた素体を別のモノに見えるよう描き足して、AI鑑定士をどこまでだませるか競うWebゲームです。

毎日の課題、ランキング、ゴーストリプレイ、シェアカードで短く遊べます。
```

## Draft QA

Run these checks before switching the itch.io page to public:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python tools/audit_launch_package.py
PYTHONPATH=src .venv310/bin/python tools/build_itchio_release_kit.py \
  --api-base https://your-api.example.com
```

Then verify manually in the itch.io draft:

- The game iframe loads the daily puzzle.
- A drawing can be submitted successfully.
- Leaderboard and ghost replay load.
- Share card opens.
- Feedback buttons record a response.
- Privacy, Terms, and Safety pages open from the app.

## API Follow-up

After the draft iframe URL is visible, set production API environment:

```bash
GITAI_CORS_ORIGINS=https://final-itch-frame-origin.example
GITAI_PUBLIC_WEB_URL=https://yourname.itch.io/gitai
```

Keep the page restricted until CORS, public URL, share cards, and one complete first-play flow pass.
