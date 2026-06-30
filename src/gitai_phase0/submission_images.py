from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image


class LocalSubmissionImageStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, submission_id: str, image: Image.Image) -> str:
        safe_id = "".join(ch for ch in submission_id if ch.isalnum() or ch in "-_")
        if not safe_id:
            raise ValueError("submission_id is not usable as an image key")
        path = self._root / f"{safe_id}.png"
        image.convert("RGBA").save(path)
        return str(path)

    def read(self, image_ref: str) -> bytes:
        path = self._path_for(image_ref)
        return path.read_bytes()

    def _path_for(self, image_ref: str) -> Path:
        if not image_ref:
            raise FileNotFoundError("submission image_ref is empty")
        if image_ref.startswith("file:"):
            return Path(image_ref.removeprefix("file:"))
        return Path(image_ref)


class MemorySubmissionImageStore:
    def __init__(self) -> None:
        self._images: dict[str, bytes] = {}

    def save(self, submission_id: str, image: Image.Image) -> str:
        buf = BytesIO()
        image.convert("RGBA").save(buf, format="PNG")
        ref = f"memory:{submission_id}"
        self._images[ref] = buf.getvalue()
        return ref

    def read(self, image_ref: str) -> bytes:
        return self._images[image_ref]
