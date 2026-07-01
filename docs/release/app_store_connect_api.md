# App Store Connect API Notes

The App Store Connect API can be used after creating an API key in App Store Connect.
Do not commit the `.p8` private key.

## Environment

```bash
cp .env.appstore.example .env.appstore
```

Expected variables:

- `ASC_KEY_ID`
- `ASC_ISSUER_ID`
- `ASC_PRIVATE_KEY_PATH`
- `ASC_BUNDLE_ID`
- `ASC_APP_SKU`
- `ASC_APP_NAME`
- `ASC_PRIMARY_LOCALE`
- `GITAI_IOS_API_BASE`
- `GITAI_IOS_SUPPORT_URL`
- `GITAI_IOS_MARKETING_URL`
- `GITAI_IOS_PRIVACY_URL`

The current iOS wrapper bundle ID is `app.gitai.game`. If App Store Connect uses
a different final bundle ID, update both `.env.appstore` and
`capacitor.config.ts`, then run:

```bash
GITAI_IOS_API_BASE=https://your-api.example.com npm run ios:sync
```

## Automatable Actions

- Create or inspect app metadata.
- Inspect build processing status.
- Manage TestFlight groups and testers.
- Update app info and version metadata.
- Attach screenshots once generated.

## Credential Check

After placing `.env.appstore` and the `.p8` key locally:

```bash
PYTHONPATH=src .venv310/bin/python tools/check_app_store_connect.py
```

This creates:

- `reports/app_store_connect/app_store_connect.md`
- `reports/app_store_connect/app_store_connect.json`

The check does not print the private key or JWT. It verifies local env fields,
generates an ES256 token, and calls the App Store Connect apps endpoint for the
configured bundle ID.

## Kept Manual

- Creating the API key and downloading the `.p8` file.
- Signing certificate/provisioning profile setup if not already handled by Xcode.
- Final review submission button if you prefer manual control.
- Responding to App Review questions.
