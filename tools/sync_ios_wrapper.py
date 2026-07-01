from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build web assets with a production API base and sync the Capacitor iOS wrapper."
    )
    parser.add_argument("--api-base", default="")
    parser.add_argument("--allow-placeholder", action="store_true")
    args = parser.parse_args()

    api_base = (
        args.api_base.strip()
        or os.environ.get("GITAI_IOS_API_BASE", "").strip()
        or os.environ.get("VITE_GITAI_API_BASE", "").strip()
    )
    if not api_base:
        raise SystemExit("Set --api-base or GITAI_IOS_API_BASE before syncing iOS.")
    if "localhost" in api_base or "127.0.0.1" in api_base:
        raise SystemExit("iOS release sync requires a non-local HTTPS API base.")
    if not api_base.startswith("https://"):
        raise SystemExit("iOS release sync requires an HTTPS API base.")
    if "example.com" in api_base and not args.allow_placeholder:
        raise SystemExit("Replace the placeholder API base, or pass --allow-placeholder for local scaffolding.")

    env = os.environ.copy()
    env["VITE_GITAI_API_BASE"] = api_base
    run(["npm", "run", "build"], env=env)
    run(["npm", "run", "ios:assets"], env=env)
    run(["npx", "cap", "sync", "ios"], env=env)
    native_config = ROOT / "ios" / "App" / "App" / "public" / "native-config.js"
    native_config.write_text(f'window.GITAI_API_BASE = "{api_base}";\n', encoding="utf-8")
    print(f"Synced iOS wrapper with API base: {api_base}")


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
