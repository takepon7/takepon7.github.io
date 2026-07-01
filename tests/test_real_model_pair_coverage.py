from __future__ import annotations

from pathlib import Path

from tools.audit_real_model_pair_coverage import audit_real_model_pair_coverage


def test_real_model_pair_coverage_reports_current_backlog(tmp_path: Path) -> None:
    report = audit_real_model_pair_coverage(out_dir=tmp_path / "real_model_pair_coverage")

    assert report["valid"] is True
    assert report["summary"]["pair_count"] == 7
    assert report["summary"]["daily_count"] == 8
    assert report["summary"]["real_model_pair_count"] == 6
    assert report["summary"]["heuristic_only_pair_count"] == 1
    assert report["summary"]["daily_real_model_ref_count"] == 6
    assert report["summary"]["daily_real_model_alternative_count"] == 7
    assert report["real_model_pair_ids"] == [
        "apple_to_baseball",
        "balloon_to_baseball",
        "book_to_car",
        "mug_to_book",
        "orange_to_tennis_ball",
        "tomato_to_baseball",
    ]
    # chair_to_car is the only pair no real model could be fooled into a usable spread.
    assert [entry["pair_id"] for entry in report["expansion_backlog"]] == ["chair_to_car"]
    assert (tmp_path / "real_model_pair_coverage" / "real_model_pair_coverage.json").exists()
