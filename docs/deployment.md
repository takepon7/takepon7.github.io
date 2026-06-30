# Deployment Notes

## Web

Build the web app with:

```bash
npm run check
```

The production web bundle defaults to same-origin API calls. This is the safest
setup when the static app and API are served under the same domain.

If the API is hosted on a separate origin, set:

```bash
VITE_GITAI_API_BASE=https://api.example.com
```

Do not leave the production build pointed at `127.0.0.1` or `localhost`; the
static smoke fails when the production bundle contains a localhost API default.

## API

Minimum production-facing environment:

```bash
GITAI_CORS_ORIGINS=https://your-public-web-origin.example
GITAI_PUBLIC_WEB_URL=https://your-public-web-origin.example
GITAI_RUNTIME_DB=/var/lib/gitai/gitai.sqlite
GITAI_IMAGE_STORE=/var/lib/gitai/submissions
GITAI_MODEL=heuristic
GITAI_OCR=fingerprint
GITAI_MODERATION=fingerprint
GITAI_SEASON_ID=season-1
GITAI_SEASON_LABEL="Season 1"
GITAI_DAILY_LLM_SPEND_CAP=100
GITAI_USER_DAILY_COMMENT_LIMIT=3
GITAI_DAILY_SUBMISSION_LIMIT=10
```

`GITAI_PUBLIC_WEB_URL` is rendered onto share cards. If it is unset, cards show
`gitai` instead of a local development URL.

## Preflight

Run:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
PYTHONPATH=src .venv310/bin/python tools/smoke_release_readiness.py --today 2026-07-06
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python -m pytest
```

Expected state:

- Static metadata and brand assets are present.
- Production JS has no localhost API default.
- Seed ghosts and first-play flow pass.
- Phase 5 budget gate passes.
- Public metadata, PWA manifest, policy pages, social creatives, and marketing docs pass.

## CI

`.github/workflows/ci.yml` runs the same production-facing checks on `main`
pushes and pull requests. Treat a failing CI run as a release blocker.
