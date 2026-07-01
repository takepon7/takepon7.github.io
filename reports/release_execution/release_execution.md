# Release Execution

- checked_at: `2026-07-01T17:24:00+09:00`
- target_web: `https://gitai.game`
- target_api: `https://api.gitai.game`
- app_store_app_id: `6786196512`

## DNS / Hosting

- `gitai.game`: DNS did not resolve from this environment.
- `api.gitai.game`: DNS did not resolve from this environment.
- Vercel CLI is installed, but no usable Vercel login/token was available in this sandbox.
- Added Vercel release configuration:
  - `vercel.json`
  - `api/index.py`
  - `requirements.txt`
  - `tools/deploy_vercel_release.sh`
- Added GitHub Pages release configuration:
  - `.github/workflows/pages.yml`
  - `web/public/CNAME`

## App Store / TestFlight

- App Store Connect app record exists for bundle ID `app.gitai.game`.
- App Store Connect build count for app `6786196512`: `0`.
- Xcode archive was attempted with the App Store Connect API key.
- Archive did not complete in this sandbox because Xcode could not access a local Apple Developer account/provisioning profile and SwiftPM/Xcode cache writes were restricted.
- Added TestFlight upload helper:
  - `tools/archive_ios_testflight.sh`

## Local Verification

- Vercel/FastAPI entrypoint loaded locally.
- `/healthz` returned `200`.
- `/` returned the app shell.
- `npm run check`: pass.
- `tools/smoke_phase3_static.py`: pass.
- `tools/smoke_public_launch.py`: pass.
- `tools/audit_launch_package.py`: pass.
- `tools/audit_app_store_release.py`: pass.
- `tools/validate_production_env.py --env-file .env.production.example --allow-placeholders`: pass.
