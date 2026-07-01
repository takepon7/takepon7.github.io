from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("GITAI_STATIC_DIR", str(ROOT / "web" / "dist"))
os.environ.setdefault("GITAI_RUNTIME_DB", "/tmp/gitai.sqlite")
os.environ.setdefault("GITAI_IMAGE_STORE", "/tmp/gitai-submissions")
os.environ.setdefault("GITAI_MODEL", "heuristic")
os.environ.setdefault("GITAI_OCR", "fingerprint")
os.environ.setdefault("GITAI_MODERATION", "fingerprint")
os.environ.setdefault("GITAI_LAYER2_ACTOR", "null")
os.environ.setdefault("GITAI_CORS_ORIGINS", "https://takepon7.github.io,capacitor://localhost")
os.environ.setdefault("GITAI_PUBLIC_WEB_URL", "https://takepon7.github.io")

from gitai_phase0.server import app  # noqa: E402
