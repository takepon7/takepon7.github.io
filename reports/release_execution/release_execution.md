# Release Execution

- checked_at: `2026-07-01T17:24:00+09:00`
- target_web: `https://takepon7.github.io`
- target_api: `https://api.gitai.game`
- app_store_app_id: `6786196512`

## DNS / Hosting

- `gitai.game`: DNS did not resolve from this environment; WHOIS reports `DOMAIN NOT FOUND`.
- `api.gitai.game`: DNS did not resolve from this environment.
- GitHub repository created: `https://github.com/takepon7/gitai`
- GitHub user-site repository target: `https://github.com/takepon7/takepon7.github.io`
- GitHub Pages enabled with Actions workflow deployment.
- GitHub Pages workflow run succeeded: `https://github.com/takepon7/gitai/actions/runs/28507241390`
- Active web URL switched to `https://takepon7.github.io` because `gitai.game` is not registered.
- Vercel CLI is installed, but no usable Vercel login/token was available in this sandbox.
- Added Vercel release configuration:
  - `vercel.json`
  - `api/index.py`
  - `requirements.txt`
  - `tools/deploy_vercel_release.sh`
- Added GitHub Pages release configuration:
  - `.github/workflows/pages.yml`

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
