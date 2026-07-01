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
VITE_GITAI_API_BASE=https://api.gitai.game
```

Do not leave the production build pointed at `127.0.0.1` or `localhost`; the
static smoke fails when the production bundle contains a localhost API default.

## API

Minimum production-facing environment:

```bash
GITAI_CORS_ORIGINS=https://gitai.game,capacitor://localhost
GITAI_PUBLIC_WEB_URL=https://gitai.game
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
  -e GITAI_CORS_ORIGINS=https://gitai.game,capacitor://localhost \
  -e GITAI_PUBLIC_WEB_URL=https://gitai.game \
  -v gitai-data:/data \
  gitai
```

When serving the app and API from the same public origin, set
`GITAI_CORS_ORIGINS` and `GITAI_PUBLIC_WEB_URL` to that origin.

Operators can review in-app content reports with:

```bash
curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  https://api.gitai.game/v1/operator/content-reports
```

Operators can review closed-playtest feedback with:

```bash
curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  https://api.gitai.game/v1/operator/playtest-feedback
```

## Vercel

The repository includes a Vercel Python Runtime entrypoint at `api/index.py`
and project configuration in `vercel.json`. The Vercel setup serves the FastAPI
app and the built `web/dist` bundle from the same project, then aliases both
`gitai.game` and `api.gitai.game` to the production deployment.

Deploy and attach domains with:

```bash
GITAI_OPERATOR_TOKEN=replace-with-long-random-token tools/deploy_vercel_release.sh
```

The script expects either an existing Vercel CLI login or `VERCEL_TOKEN` in the
environment. It can add the domains to the Vercel project, but registrar DNS
still has to delegate or point `gitai.game` to Vercel if the domain is managed
outside Vercel.

The Vercel fallback stores runtime SQLite and submitted images under `/tmp`.
That is enough for a smokeable deployment, but serious public traffic should use
a persistent container volume or managed database/blob storage before promotion.

## GitHub Pages

GitHub Pages can host the static web app at `https://gitai.game`. It cannot run
the FastAPI service, so `api.gitai.game` still needs a separate API host.

The repository includes `.github/workflows/pages.yml`, which builds `web/dist`
with:

```bash
VITE_GITAI_API_BASE=https://api.gitai.game npm run build
```

and deploys the artifact to GitHub Pages. The custom domain is set by
`web/public/CNAME`.

DNS for `gitai.game` should point to GitHub Pages. Keep `api.gitai.game`
pointing at the API host.

Recommended apex records for `gitai.game`:

```text
@  A     185.199.108.153
@  A     185.199.109.153
@  A     185.199.110.153
@  A     185.199.111.153
@  AAAA  2606:50c0:8000::153
@  AAAA  2606:50c0:8001::153
@  AAAA  2606:50c0:8002::153
@  AAAA  2606:50c0:8003::153
```

GitHub also recommends adding the custom domain in the repository Pages
settings before changing DNS, and avoiding wildcard DNS records for Pages.

## Preflight

Run:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
PYTHONPATH=src .venv310/bin/python tools/smoke_release_readiness.py --today 2026-07-06
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python tools/validate_production_env.py --env-file .env.production
PYTHONPATH=src .venv310/bin/python tools/audit_real_model_pair_coverage.py
PYTHONPATH=src .venv310/bin/python tools/audit_launch_package.py
PYTHONPATH=src .venv310/bin/python -m pytest
```

Expected state:

- Static metadata and brand assets are present.
- Production JS has no localhost API default.
- Seed ghosts and first-play flow pass.
- Phase 5 budget gate passes.
- Public metadata, PWA manifest, policy pages, social creatives, and marketing docs pass.
- Production env validation rejects placeholder origins, browser localhost origins, unsafe moderation bypasses, and weak operator tokens while accepting the native `capacitor://localhost` app origin.
- Real-model pair coverage audit reports the measured-pair expansion backlog.
- Launch package audit gathers release, first-play, marketing, policy, and imagegen asset evidence.
- Same-origin web serving from the API is ready when `GITAI_STATIC_DIR` points at `web/dist`.

## CI

`.github/workflows/ci.yml` runs the same production-facing checks on `main`
pushes and pull requests. Treat a failing CI run as a release blocker.
