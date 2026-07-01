# Production API Status

- checked_at: `2026-07-01T20:03:16+09:00`
- valid: `false`
- target_api: `https://api.gitai.game`

## DNS

- `gitai.game`: `DOMAIN NOT FOUND`
- `api.gitai.game`: unresolved

`api.gitai.game` cannot be configured until `gitai.game` is registered at a
domain registrar.

## Vercel

- CLI installed: `true`
- CLI version: `54.5.0`
- token_present: `false`
- authenticated: `false`

The FastAPI service is prepared for Vercel, but deployment requires an existing
Vercel CLI login or `VERCEL_TOKEN`.

## Local API

- API entrypoint import: pass

## Remaining Blockers

- Register `gitai.game` before configuring `api.gitai.game` DNS.
- Provide a Vercel login or `VERCEL_TOKEN` before deploying the FastAPI service.
