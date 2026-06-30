from __future__ import annotations

from pathlib import Path

from tools.audit_launch_package import audit_launch_package


def test_launch_package_audit_accepts_current_package(tmp_path: Path) -> None:
    report = audit_launch_package(out_dir=tmp_path / "launch_package_audit")

    assert report["valid"] is True
    assert report["summary"]["failed_checks"] == 0
    assert any(item["name"] == "release_readiness_valid" for item in report["checks"])
    assert any(item["name"] == "public_launch_valid" for item in report["checks"])
    assert any(item["name"] == "first_play_flow_valid" for item in report["checks"])
    assert any(item["name"] == "imagegen_assets_ready" for item in report["checks"])
    assert any(item["name"] == "closed_playtest_kit_ready" for item in report["checks"])
    assert any(item["name"] == "production_env_template_ready" for item in report["checks"])
    assert any(item["name"] == "real_model_expansion_backlog_ready" for item in report["checks"])
    assert len(report["manual_followups"]) == 3
    assert (tmp_path / "launch_package_audit" / "launch_package_audit.json").exists()
