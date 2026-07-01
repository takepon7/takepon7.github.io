# Final Release URLs

The App Store release currently uses GitHub Pages for the public web surface.
The `gitai.game` domain is not registered yet, so it remains a future branded
domain option rather than the active launch URL.

| Purpose | URL |
| --- | --- |
| Web / marketing | `https://takepon7.github.io` |
| API | `https://api.gitai.game` |
| Support | `https://takepon7.github.io/support.html` |
| Privacy Policy | `https://takepon7.github.io/privacy.html` |
| Terms of Use | `https://takepon7.github.io/terms.html` |
| Safety Guidelines | `https://takepon7.github.io/safety.html` |
| iOS native origin | `capacitor://localhost` |

Production API environment:

```bash
GITAI_CORS_ORIGINS=https://takepon7.github.io,capacitor://localhost
GITAI_PUBLIC_WEB_URL=https://takepon7.github.io
```

iOS wrapper build:

```bash
GITAI_IOS_API_BASE=https://api.gitai.game npm run ios:sync
```

App Store Connect URL fields:

```bash
GITAI_IOS_SUPPORT_URL=https://takepon7.github.io/support.html
GITAI_IOS_MARKETING_URL=https://takepon7.github.io
GITAI_IOS_PRIVACY_URL=https://takepon7.github.io/privacy.html
```

Before App Review, `api.gitai.game` still needs to point to the FastAPI service.
GitHub Pages is not suitable for `api.gitai.game` because Pages only serves
static files. Register `gitai.game` before attempting to configure
`api.gitai.game`; until the parent domain exists at a registrar, no DNS provider
can create a working `api.gitai.game` record.
