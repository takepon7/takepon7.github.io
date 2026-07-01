# Final Release URLs

The App Store release uses the `gitai.game` public domain family.

| Purpose | URL |
| --- | --- |
| Web / marketing | `https://gitai.game` |
| API | `https://api.gitai.game` |
| Support | `https://gitai.game/support.html` |
| Privacy Policy | `https://gitai.game/privacy.html` |
| Terms of Use | `https://gitai.game/terms.html` |
| Safety Guidelines | `https://gitai.game/safety.html` |
| iOS native origin | `capacitor://localhost` |

Production API environment:

```bash
GITAI_CORS_ORIGINS=https://gitai.game,capacitor://localhost
GITAI_PUBLIC_WEB_URL=https://gitai.game
```

iOS wrapper build:

```bash
GITAI_IOS_API_BASE=https://api.gitai.game npm run ios:sync
```

App Store Connect URL fields:

```bash
GITAI_IOS_SUPPORT_URL=https://gitai.game/support.html
GITAI_IOS_MARKETING_URL=https://gitai.game
GITAI_IOS_PRIVACY_URL=https://gitai.game/privacy.html
```

Before TestFlight, DNS and hosting must point `gitai.game` to the public web app
and `api.gitai.game` to the FastAPI service.
