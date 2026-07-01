from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / "web" / "dist"
DEFAULT_OUT_DIR = ROOT / "releases" / "itchio"
DEFAULT_REPORT_DIR = ROOT / "reports" / "itchio_release"
REQUIRED_ROOT_FILES = ("index.html", "privacy.html", "terms.html", "safety.html", "site.webmanifest")
REQUIRED_BRAND_FILES = (
    "brand/app-icon-192.png",
    "brand/app-icon-512.png",
    "brand/favicon-32.png",
    "brand/og-image.png",
    "brand/social-feed-square.png",
    "brand/social-story-vertical.png",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the itch.io HTML5 web release zip and release evidence."
    )
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--version", default=package_version())
    parser.add_argument("--api-base", default=os.environ.get("VITE_GITAI_API_BASE", ""))
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run npm run build before packaging. If --api-base is set it is passed to Vite.",
    )
    args = parser.parse_args()

    if args.build:
        env = os.environ.copy()
        if args.api_base:
            env["VITE_GITAI_API_BASE"] = args.api_base
        subprocess.run(["npm", "run", "build"], cwd=ROOT, env=env, check=True)

    report = build_release_kit(
        dist=args.dist,
        out_dir=args.out_dir,
        report_dir=args.report_dir,
        version=args.version,
        api_base=args.api_base.strip(),
    )
    print(f"Wrote {report['artifact']['zip_path']}")
    print(f"Wrote {args.report_dir / 'itchio_release.json'}")
    print(f"Wrote {args.report_dir / 'itchio_release.md'}")
    print(f"ready_for_public_upload={str(report['summary']['ready_for_public_upload']).lower()}")


def build_release_kit(
    dist: Path,
    out_dir: Path,
    report_dir: Path,
    version: str,
    api_base: str,
) -> dict:
    dist = dist.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    slug = f"gitai-itchio-web-v{version}"
    zip_path = out_dir / f"{slug}.zip"
    manifest_path = out_dir / f"{slug}.manifest.json"

    files = list_dist_files(dist)
    checks = build_checks(dist=dist, files=files, api_base=api_base)
    write_zip(dist=dist, files=files, zip_path=zip_path)
    manifest = build_manifest(dist=dist, files=files, zip_path=zip_path, api_base=api_base, version=version)
    write_json(manifest_path, manifest)

    ready = all(check["status"] == "pass" for check in checks)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "ready_for_public_upload": ready,
            "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
            "failed_checks": sum(1 for check in checks if check["status"] == "fail"),
            "manual_followups": [
                "Upload the zip to an itch.io draft page as an HTML5/browser-playable file.",
                "After itch.io assigns the final game frame origin, add that origin to GITAI_CORS_ORIGINS.",
                "Set GITAI_PUBLIC_WEB_URL to the public itch.io project URL before public promotion.",
            ],
        },
        "artifact": {
            "zip_path": str(zip_path),
            "manifest_path": str(manifest_path),
            "zip_sha256": sha256_file(zip_path),
            "zip_bytes": zip_path.stat().st_size,
            "file_count": len(files),
            "version": version,
            "api_base": api_base,
        },
        "itchio_page": page_metadata(),
        "checks": checks,
    }
    write_json(report_dir / "itchio_release.json", report)
    (report_dir / "itchio_release.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def list_dist_files(dist: Path) -> list[Path]:
    if not dist.exists():
        raise SystemExit(f"dist does not exist: {dist}")
    return sorted(path for path in dist.rglob("*") if path.is_file())


def build_checks(dist: Path, files: list[Path], api_base: str) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    rels = {path.relative_to(dist).as_posix() for path in files}
    for required in REQUIRED_ROOT_FILES:
        checks.append(check(f"root_{required}_exists", required in rels, required))
    checks.append(check("assets_directory_exists", any(rel.startswith("assets/") for rel in rels), "assets/*"))
    for required in REQUIRED_BRAND_FILES:
        checks.append(check(f"brand_{Path(required).stem}_exists", required in rels, required))

    bundle_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in files
        if path.suffix in {".html", ".js", ".css", ".json", ".webmanifest", ".txt"}
    )
    has_localhost = "localhost" in bundle_text or "127.0.0.1" in bundle_text
    checks.append(check("bundle_has_no_localhost_api", not has_localhost, "no localhost/127.0.0.1"))
    checks.append(
        check(
            "external_api_base_configured_for_itchio",
            bool(api_base),
            api_base or "set --api-base to the deployed API origin before public upload",
        )
    )
    checks.append(check("zip_root_will_contain_index", "index.html" in rels, "index.html at zip root"))
    return checks


def check(name: str, ok: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "pass" if ok else "fail", "detail": detail}


def write_zip(dist: Path, files: list[Path], zip_path: Path) -> None:
    tmp_path = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(dist).as_posix())
    tmp_path.replace(zip_path)


def build_manifest(dist: Path, files: list[Path], zip_path: Path, api_base: str, version: str) -> dict:
    return {
        "name": "gitai",
        "channel": "itchio-web",
        "version": version,
        "api_base": api_base,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": sha256_file(zip_path),
        },
        "files": [
            {
                "path": path.relative_to(dist).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }


def page_metadata() -> dict:
    return {
        "title": "gitai",
        "short_text": "絵でAI鑑定士をだます、毎日更新の擬態ドローイングゲーム。",
        "genre": ["Puzzle", "Drawing", "AI"],
        "tags": ["drawing", "puzzle", "web", "async", "leaderboard"],
        "release_status": "prototype / public playtest",
        "pricing": "Free or pay what you want",
        "embed": {
            "kind": "HTML5",
            "viewport": "1280x720 or responsive fullscreen",
            "mobile_friendly": True,
        },
        "description": (
            "りんごを野球ボールに、椅子を車に。gitai は、与えられた素体を別のモノに"
            "見えるよう描き足して、AI鑑定士をどこまでだませるか競うWebゲームです。"
            "毎日の課題、ランキング、ゴーストリプレイ、シェアカードで短く遊べます。"
        ),
    }


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    artifact = report["artifact"]
    page = report["itchio_page"]
    lines = [
        "# itch.io Web Release Kit",
        "",
        f"- ready_for_public_upload: `{str(summary['ready_for_public_upload']).lower()}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        f"- zip: `{artifact['zip_path']}`",
        f"- zip_sha256: `{artifact['zip_sha256']}`",
        f"- zip_bytes: `{artifact['zip_bytes']}`",
        f"- file_count: `{artifact['file_count']}`",
        f"- api_base: `{artifact['api_base'] or 'not set'}`",
        "",
        "## Upload",
        "",
        "1. Create or open an itch.io draft project.",
        "2. Set project kind to HTML/browser playable.",
        "3. Upload the zip above and mark it as playable in browser.",
        "4. Keep the page restricted until the live API origin and CORS origin are verified.",
        "5. After the iframe loads, submit one drawing, open one share card, and record feedback once.",
        "",
        "## Page Metadata",
        "",
        f"- title: `{page['title']}`",
        f"- short_text: {page['short_text']}",
        f"- release_status: `{page['release_status']}`",
        f"- pricing: `{page['pricing']}`",
        f"- tags: {', '.join(page['tags'])}",
        f"- viewport: `{page['embed']['viewport']}`",
        "",
        "## Description",
        "",
        page["description"],
        "",
        "## Checks",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    for check_item in report["checks"]:
        lines.append(f"| {check_item['name']} | {check_item['status']} | {check_item['detail']} |")
    lines.extend(
        [
            "",
            "## Manual Follow-ups",
            "",
            *[f"- {item}" for item in summary["manual_followups"]],
            "",
            "## Official References",
            "",
            "- https://itch.io/docs/creators/html5",
            "- https://itch.io/docs/butler/",
        ]
    )
    return "\n".join(lines) + "\n"


def package_version() -> str:
    package_json = ROOT / "package.json"
    if not package_json.exists():
        return "0.1.0"
    payload = json.loads(package_json.read_text(encoding="utf-8"))
    return str(payload.get("version", "0.1.0"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
