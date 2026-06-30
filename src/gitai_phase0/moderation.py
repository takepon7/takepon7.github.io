from __future__ import annotations

from pathlib import Path

from PIL import Image

from gitai_phase0.domain import CaseSpec
from gitai_phase0.repositories import image_fingerprint, load_json


class NullImageModerator:
    def moderate(self, image: Image.Image, case: CaseSpec | None = None) -> str:
        del image, case
        return "pass"


class ImageFingerprintModerator:
    def __init__(self, path: Path) -> None:
        if path.exists():
            self._fixtures = {
                str(item["fingerprint"]): normalize_moderation(str(item.get("moderation", "pass")))
                for item in load_json(path).get("fixtures", ())
            }
        else:
            self._fixtures = {}

    def moderate(self, image: Image.Image, case: CaseSpec | None = None) -> str:
        del case
        return self._fixtures.get(image_fingerprint(image), "pass")


def normalize_moderation(value: str) -> str:
    return "flag" if value == "flag" else "pass"
