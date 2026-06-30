from __future__ import annotations

from typing import Protocol

import numpy as np
from PIL import Image

from gitai_phase0.domain import CaseSpec, TemplateSet


class JudgeModel(Protocol):
    @property
    def model_version(self) -> str:
        raise NotImplementedError

    def encode_image(self, image: Image.Image) -> np.ndarray:
        raise NotImplementedError

    def encode_text(self, label: str, template_set: TemplateSet) -> np.ndarray:
        raise NotImplementedError


class OcrScanner(Protocol):
    def scan(self, image: Image.Image, case: CaseSpec | None = None) -> tuple[str, ...]:
        raise NotImplementedError


class ImageModerator(Protocol):
    def moderate(self, image: Image.Image, case: CaseSpec | None = None) -> str:
        raise NotImplementedError
