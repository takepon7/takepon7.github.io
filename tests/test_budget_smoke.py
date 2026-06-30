from __future__ import annotations

from pathlib import Path

from gitai_phase0.budget_smoke import run_appraisal_budget_smoke


def test_appraisal_budget_smoke_caps_spend_and_degrades(tmp_path: Path) -> None:
    report = run_appraisal_budget_smoke(
        runtime_db=tmp_path / "budget.sqlite",
        pairs_path=Path("data/scoring/pairs.json"),
        request_count=12,
        daily_cap_units=5,
        user_daily_limit=12,
    )

    status_counts = {item.status: item.count for item in report.status_counts}
    assert report.gate_passed is True
    assert report.daily_spend == 5
    assert status_counts == {"fallback_budget": 7, "minted": 5}
