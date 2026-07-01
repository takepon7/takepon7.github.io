# Release Execution

- checked_at: `2026-07-01T20:03:16+09:00`
- target_web: `https://takepon7.github.io`
- target_api: `https://api.gitai.game`
- app_store_app_id: `6786196512`

## DNS / Hosting

- `gitai.game`: DNS did not resolve from this environment; WHOIS reports `DOMAIN NOT FOUND`.
- `api.gitai.game`: DNS did not resolve from this environment.
- GitHub repository created: `https://github.com/takepon7/gitai`
- GitHub user-site repository target: `https://github.com/takepon7/takepon7.github.io`
- Disabled the obsolete `takepon7/gitai` Pages setting that still pointed at unregistered `gitai.game`.
- GitHub Pages enabled with Actions workflow deployment.
- Pages workflow is guarded so only `takepon7/takepon7.github.io` publishes the public site.
- GitHub Pages user-site build type switched from legacy branch publishing to workflow artifacts.
- GitHub Pages workflow run succeeded: `https://github.com/takepon7/takepon7.github.io/actions/runs/28509749468`
- Active web URL switched to `https://takepon7.github.io` because `gitai.game` is not registered.
- Public web checks passed:
  - `https://takepon7.github.io/`: `200`
  - `https://takepon7.github.io/privacy.html`: `200`
  - `https://takepon7.github.io/support.html`: `200`
- Vercel CLI is installed, but no usable Vercel login/token was available in this sandbox.
- Vercel CLI version is `54.5.0`; upgrade to the latest CLI before final deployment.
- Production API deployment remains blocked because `gitai.game` is not registered and no Vercel login/token is available.
- Updated Vercel/FastAPI defaults to allow the active web origin `https://takepon7.github.io`.
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
- Latest Xcode upload succeeded and is in Apple processing; the build has not appeared in the App Store Connect builds API yet.
- App Store version `1.0` is in `PREPARE_FOR_SUBMISSION`.
- App Store text and URL metadata synced through the App Store Connect API.
- 6.9-inch screenshot set generated and audited: `5`.
- Internal TestFlight beta group exists.
- Xcode archive was attempted with the App Store Connect API key.
- Archive did not complete in this sandbox because SwiftPM package resolution invokes Apple tooling that is blocked by the Codex sandbox.
- Added TestFlight upload helper:
  - `tools/archive_ios_testflight.sh`
- Added TestFlight/App Review readiness audit:
  - `tools/audit_testflight_review_readiness.py`

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
- GitHub Pages public URL smoke: pass.
