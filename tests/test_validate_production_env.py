from __future__ import annotations

from pathlib import Path

from tools.validate_production_env import parse_env_file, validate_production_env


def test_production_env_example_passes_template_validation() -> None:
    env = parse_env_file(Path(".env.production.example"))

    report = validate_production_env(
        env,
        source=".env.production.example",
        allow_placeholders=True,
    )

    assert report["valid"] is True
    assert report["summary"]["failed_checks"] == 0
    assert any(item["name"] == "operator_token_is_strong" for item in report["checks"])
    assert report["warnings"]


def test_production_env_strict_validation_rejects_placeholders_and_unsafe_guards() -> None:
    env = parse_env_file(Path(".env.production.example"))
    env.update(
        {
            "GITAI_PUBLIC_WEB_URL": "http://localhost:5173",
            "GITAI_CORS_ORIGINS": "https://your-public-web-origin.example,http://localhost:5173",
            "GITAI_MODERATION": "none",
            "GITAI_OPERATOR_TOKEN": "replace-with-long-random-token",
        }
    )

    report = validate_production_env(env, source="bad-env")

    assert report["valid"] is False
    error_text = "\n".join(report["errors"])
    assert "public_web_url_is_https" in error_text
    assert "cors_origins_are_production_origins" in error_text
    assert "model_and_guards_are_production_safe" in error_text
    assert "operator_token_is_strong" in error_text


def test_production_env_strict_validation_accepts_realistic_values() -> None:
    env = parse_env_file(Path(".env.production.example"))
    env.update(
        {
            "GITAI_PUBLIC_WEB_URL": "https://play.gitai.app",
            "GITAI_CORS_ORIGINS": "https://play.gitai.app,capacitor://localhost",
            "GITAI_STATIC_DIR": "/app/web/dist",
            "GITAI_RUNTIME_DB": "/data/gitai.sqlite",
            "GITAI_IMAGE_STORE": "/data/submissions",
            "GITAI_OPERATOR_TOKEN": "prod_9Jm2Qx7Va4Tz8Nw3Lk6Rb5Yc1Hs0Pf",
        }
    )

    report = validate_production_env(env, source="realistic-env")

    assert report["valid"] is True
    assert report["summary"]["failed_checks"] == 0
