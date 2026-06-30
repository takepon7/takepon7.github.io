from __future__ import annotations

from pathlib import Path

from tools.smoke_public_launch import smoke_public_launch


def test_public_launch_smoke_accepts_current_build(tmp_path: Path) -> None:
    report = smoke_public_launch(
        web_dist_dir=Path("web/dist"),
        out_dir=tmp_path / "public_launch",
    )

    assert report["valid"] is True
    assert report["summary"]["failed_checks"] == 0
    assert any(item["name"] == "production_api_not_localhost" for item in report["checks"])
    assert any(item["name"] == "brand_images_have_expected_sizes" for item in report["checks"])
    assert any(item["name"] == "public_policy_pages_ready" for item in report["checks"])
    assert (tmp_path / "public_launch" / "public_launch.json").exists()
