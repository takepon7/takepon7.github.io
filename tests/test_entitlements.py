from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gitai_phase0.entitlement_repositories import SqliteEntitlementRepository


def test_redeem_code_grants_premium_once_per_user_until_limit(tmp_path) -> None:
    repo = SqliteEntitlementRepository(tmp_path / "entitlements.sqlite")
    repo.seed_redeem_code("founder-pass", max_redemptions=1)

    first = repo.redeem_premium_code("player-a", " founder-pass ")
    duplicate = repo.redeem_premium_code("player-a", "FOUNDER-PASS")
    exhausted = repo.redeem_premium_code("player-b", "FOUNDER-PASS")

    assert first.status == "redeemed"
    assert first.premium is True
    assert duplicate.status == "already_redeemed"
    assert duplicate.premium is True
    assert exhausted.status == "exhausted"
    assert exhausted.premium is False
    assert repo.has_premium_access("player-a") is True
    assert repo.has_premium_access("player-b") is False


def test_redeem_code_rejects_expired_and_unknown_codes(tmp_path) -> None:
    repo = SqliteEntitlementRepository(tmp_path / "entitlements.sqlite")
    now = datetime(2026, 6, 29, tzinfo=timezone.utc)
    repo.seed_redeem_code("expired", expires_at=now - timedelta(seconds=1))

    expired = repo.redeem_premium_code("player", "expired", now=now)
    invalid = repo.redeem_premium_code("player", "unknown", now=now)

    assert expired.status == "expired"
    assert invalid.status == "invalid"
    assert repo.has_premium_access("player") is False
