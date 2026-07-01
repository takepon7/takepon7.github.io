# App Store Release Plan

## Target Shape

Ship `gitai` as an iPhone app backed by the production API.

Fastest implementation path:

- iOS shell: Capacitor or native `WKWebView`
- Web UI: existing `web/dist`
- API: existing FastAPI service on a production HTTPS origin
- Distribution: TestFlight first, then App Store review
- Automation: App Store Connect API for metadata/build status where useful

## Release Gates

1. Production API is live on HTTPS.
2. iOS app points at the production API, not localhost.
3. First-play flow passes on device or simulator.
4. Privacy, Terms, and Safety URLs are reachable.
5. App Store screenshots are generated at 6.9-inch size.
6. TestFlight internal build is installable.
7. Review notes explain user-generated drawings, moderation, reporting, and no-login flow.

Current App Store Connect record:

- Bundle ID: `app.gitai.game`
- Bundle resource ID: `32QLDGB33V`
- App ID: `6786196512`
- SKU: `gitai-ios`

Final release URLs:

- Web / marketing: `https://takepon7.github.io`
- API: `https://api.gitai.game`
- Support: `https://takepon7.github.io/support.html`
- Privacy: `https://takepon7.github.io/privacy.html`
- Terms: `https://takepon7.github.io/terms.html`
- Safety: `https://takepon7.github.io/safety.html`
- Native CORS origin: `capacitor://localhost`

## Suggested Build Path

### Phase 1: iOS Wrapper

- Create an iOS target with bundle ID from `.env.appstore.example`.
- Load the app locally from bundled web assets or from the production web URL.
- Prefer bundled assets plus `GITAI_IOS_API_BASE` injected at build time.
- Add a first-run offline/error screen for API failures.
- Ensure external policy URLs open in Safari or an in-app browser sheet.

The repository now includes a Capacitor iOS shell in `ios/` with bundle ID
`app.gitai.game`.

To refresh the bundled iOS web assets:

```bash
GITAI_IOS_API_BASE=https://api.gitai.game npm run ios:sync
```

To open the project in Xcode:

```bash
npm run ios:open
```

### Phase 2: API Production

- Deploy the existing Docker/FastAPI app.
- Set:
  - `GITAI_PUBLIC_WEB_URL`
  - `GITAI_RUNTIME_DB`
  - `GITAI_IMAGE_STORE`
  - `GITAI_MODEL`
  - `GITAI_OCR`
  - `GITAI_MODERATION`
  - `GITAI_OPERATOR_TOKEN`
- Run release smoke checks and one first-play submission.

### Phase 3: TestFlight

- Use the existing App Store Connect app record.
- Upload an archive build.
- Add internal testers.
- Verify:
  - launch
  - daily puzzle fetch
  - drawing submission
  - leaderboard
  - ghost replay
  - feedback
  - share card

The repository includes a direct archive/upload helper:

```bash
APPLE_TEAM_ID=MC77VJ8M9D tools/archive_ios_testflight.sh
```

This script refreshes the bundled web assets, archives the Capacitor app, and
exports with `destination=upload` for App Store Connect/TestFlight. It requires
the Apple Developer account to be available to Xcode or the App Store Connect API
key from `.env.appstore` to be accepted for provisioning updates.

By default, the export is suitable for review-candidate TestFlight builds:
`testFlightInternalTestingOnly` is set to `false`. For a throwaway internal-only
build, run with `TESTFLIGHT_INTERNAL_ONLY=true`.

### Phase 4: App Review

- Fill metadata from `docs/release/app_store_metadata_ja.md`.
- Upload screenshots from `reports/app_store/screenshots/iphone-6.9/`.
- Include review notes from metadata doc.
- Submit with manual release first.

## App Store Connect API Inputs

Keep credentials outside git:

```bash
cp .env.appstore.example .env.appstore
```

Required values:

- `ASC_KEY_ID`
- `ASC_ISSUER_ID`
- `ASC_PRIVATE_KEY_PATH`
- `ASC_BUNDLE_ID`
- `ASC_APP_SKU`
- `ASC_APP_NAME`
- `GITAI_IOS_API_BASE`
- `GITAI_IOS_SUPPORT_URL`
- `GITAI_IOS_MARKETING_URL`
- `GITAI_IOS_PRIVACY_URL`

## Screenshot Generation

Generate the first 6.9-inch screenshot set with:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_app_store_screenshots.py
PYTHONPATH=src .venv310/bin/python tools/audit_app_store_release.py
PYTHONPATH=src .venv310/bin/python tools/audit_testflight_review_readiness.py
```

Outputs:

- `reports/app_store/screenshots/raw/`
- `reports/app_store/screenshots/generated/iphone-6.9/`
- `reports/app_store/app_store_release.md`
- `reports/testflight_review/testflight_review_readiness.md`

## Manual Follow-ups

- Apple Developer account must be available to Xcode for signing, or automatic
  provisioning must succeed with the App Store Connect API key.
- Production API must be deployed at `https://api.gitai.game` before final iOS build.
- Run `tools/archive_ios_testflight.sh` from a normal local terminal after DNS/hosting are live.
- App review screenshots must be generated from the final UI/API build.
