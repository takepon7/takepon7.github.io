from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from gitai_phase0.moderation import ImageFingerprintModerator, NullImageModerator
from gitai_phase0.repositories import image_fingerprint


def test_null_image_moderator_passes() -> None:
    assert NullImageModerator().moderate(Image.new("RGBA", (8, 8), "white")) == "pass"


def test_fingerprint_moderator_flags_fixture(tmp_path: Path) -> None:
    image = Image.new("RGBA", (8, 8), "red")
    fixture = {
        "fixtures": [
            {
                "fingerprint": image_fingerprint(image),
                "moderation": "flag",
            }
        ]
    }
    path = tmp_path / "moderation_fixtures.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    moderator = ImageFingerprintModerator(path)

    assert moderator.moderate(image) == "flag"
    assert moderator.moderate(Image.new("RGBA", (8, 8), "blue")) == "pass"
