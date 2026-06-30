# Deployment Notes

## Web

Build the web app with:

```bash
npm run check
```

The production web bundle defaults to same-origin API calls. This is the safest
setup when the static app and API are served under the same domain.

To serve the built web app from the API process, build the web bundle and set:

```bash
GITAI_STATIC_DIR=/app/web/dist
```

With `GITAI_STATIC_DIR` set, the API keeps `/v1/*` and `/healthz` as API routes
and serves `/`, policy pages, icons, and other static assets from the web dist.

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
GITAI_STATIC_DIR=/app/web/dist
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
GITAI_OPERATOR_TOKEN=replace-with-long-random-token
```

`GITAI_PUBLIC_WEB_URL` is rendered onto share cards. If it is unset, cards show
`gitai` instead of a local development URL.

## Container

The included `Dockerfile` builds the web bundle with Node, copies it into the
Python runtime image, sets `GITAI_STATIC_DIR=/app/web/dist`, creates `/data`,
switches to a non-root `gitai` user, adds a `/healthz` container healthcheck,
and starts uvicorn on port `8000`.

Example:

```bash
docker build -t gitai .
docker run --rm -p 8000:8000 \
  -e GITAI_CORS_ORIGINS=https://your-public-web-origin.example \
  -e GITAI_PUBLIC_WEB_URL=https://your-public-web-origin.example \
  -v gitai-data:/data \
  gitai
```

When serving the app and API from the same public origin, set
`GITAI_CORS_ORIGINS` and `GITAI_PUBLIC_WEB_URL` to that origin.

Operators can review in-app content reports with:

```bash
curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  https://your-public-web-origin.example/v1/operator/content-reports
```

Operators can review closed-playtest feedback with:

```bash
curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  https://your-public-web-origin.example/v1/operator/playtest-feedback
```

## Preflight

Run:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
PYTHONPATH=src .venv310/bin/python tools/smoke_release_readiness.py --today 2026-07-06
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python tools/validate_production_env.py --env-file .env.production
PYTHONPATH=src .venv310/bin/python tools/audit_launch_package.py
PYTHONPATH=src .venv310/bin/python -m pytest
```

Expected state:

- Static metadata and brand assets are present.
- Production JS has no localhost API default.
- Seed ghosts and first-play flow pass.
- Phase 5 budget gate passes.
- Public metadata, PWA manifest, policy pages, social creatives, and marketing docs pass.
- Production env validation rejects placeholder origins, localhost origins, unsafe moderation bypasses, and weak operator tokens.
- Launch package audit gathers release, first-play, marketing, policy, and imagegen asset evidence.
- Same-origin web serving from the API is ready when `GITAI_STATIC_DIR` points at `web/dist`.

## CI

`.github/workflows/ci.yml` runs the same production-facing checks on `main`
pushes and pull requests. Treat a failing CI run as a release blocker.
