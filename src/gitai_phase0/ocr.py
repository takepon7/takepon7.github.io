from __future__ import annotations

from PIL import Image

from gitai_phase0.domain import CaseSpec


class KnownTextOcrScanner:
    """Fixture scanner for Phase 0 samples with explicit known text metadata."""

    def scan(self, image: Image.Image, case: CaseSpec | None = None) -> tuple[str, ...]:
        del image
        if case is None:
            return ()
        return case.known_text


class NullOcrScanner:
    def scan(self, image: Image.Image, case: CaseSpec | None = None) -> tuple[str, ...]:
        del image, case
        return ()


class TesseractOcrScanner:
    def __init__(self) -> None:
        try:
            import pytesseract
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract is not installed. Install the optional 'ocr' extra."
            ) from exc
        self._pytesseract = pytesseract

    def scan(self, image: Image.Image, case: CaseSpec | None = None) -> tuple[str, ...]:
        del case
        text = self._pytesseract.image_to_string(image.convert("RGB"))
        return tuple(part.strip() for part in text.splitlines() if part.strip())
