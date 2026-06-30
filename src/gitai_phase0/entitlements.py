from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PremiumRedeemStatus = Literal["redeemed", "already_redeemed", "invalid", "expired", "exhausted"]


@dataclass(frozen=True)
class PremiumEntitlement:
    user_id: str
    source: str
    granted_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True)
class PremiumRedeemResult:
    user_id: str
    code: str
    status: PremiumRedeemStatus
    premium: bool


def normalize_redeem_code(value: str) -> str:
    cleaned = "".join(
        char.upper()
        for char in value.strip()
        if char.isascii() and (char.isalnum() or char == "-")
    )
    return cleaned[:32]


def entitlement_is_active(entitlement: PremiumEntitlement, now: datetime) -> bool:
    return entitlement.expires_at is None or entitlement.expires_at > now
