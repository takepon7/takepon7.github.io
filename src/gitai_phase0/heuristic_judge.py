from __future__ import annotations

import re

import numpy as np
from PIL import Image

from gitai_phase0.domain import TemplateSet
from gitai_phase0.scoring import normalize_vector


class HeuristicJudge:
    """Deterministic local judge for plumbing tests.

    This is not a CLIP replacement. It gives predictable behavior for synthetic
    samples so the scoring path, OCR hard-zero, and tau sweep can run offline.
    """

    model_version = "heuristic-color-shape-v1"

    def encode_image(self, image: Image.Image) -> np.ndarray:
        rgba = image.convert("RGBA")
        pixels = np.asarray(rgba, dtype=np.float32)
        rgb = pixels[:, :, :3]
        alpha = pixels[:, :, 3] / 255.0
        mask = alpha > 0.05
        if not bool(mask.any()):
            mask = np.mean(rgb, axis=2) < 245.0
        if not bool(mask.any()):
            mask = np.ones(alpha.shape, dtype=bool)

        obj = rgb[mask]
        red = ratio(obj, (obj[:, 0] > 150) & (obj[:, 0] > obj[:, 1] * 1.25) & (obj[:, 0] > obj[:, 2] * 1.25))
        green = ratio(obj, (obj[:, 1] > 120) & (obj[:, 1] > obj[:, 0] * 1.15) & (obj[:, 1] > obj[:, 2] * 1.15))
        yellow = ratio(obj, (obj[:, 0] > 165) & (obj[:, 1] > 140) & (obj[:, 2] < 120))
        white = ratio(obj, (obj[:, 0] > 210) & (obj[:, 1] > 210) & (obj[:, 2] > 210))
        dark = ratio(obj, (obj[:, 0] < 85) & (obj[:, 1] < 85) & (obj[:, 2] < 85))
        edge = edge_density(rgb, mask)
        circularity = bbox_fill(mask)
        blue = ratio(obj, (obj[:, 2] > 130) & (obj[:, 2] > obj[:, 0] * 1.15) & (obj[:, 2] > obj[:, 1] * 1.15))

        return normalize_vector(
            np.array([red, green, yellow, white, dark, edge, circularity, blue], dtype=np.float32)
        )

    def encode_text(self, label: str, template_set: TemplateSet) -> np.ndarray:
        del template_set
        key = canonicalize(label)
        vector = PROTOTYPES.get(key, PROTOTYPES["generic"])
        return normalize_vector(np.asarray(vector, dtype=np.float32))


def ratio(obj: np.ndarray, predicate: np.ndarray) -> float:
    if len(obj) == 0:
        return 0.0
    return float(np.count_nonzero(predicate) / len(obj))


def bbox_fill(mask: np.ndarray) -> float:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return 0.0
    area = float(mask.sum())
    bbox_area = float((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))
    return area / bbox_area if bbox_area else 0.0


def edge_density(rgb: np.ndarray, mask: np.ndarray) -> float:
    gray = np.mean(rgb, axis=2)
    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    xmask = mask[:, 1:] & mask[:, :-1]
    ymask = mask[1:, :] & mask[:-1, :]
    edges = 0
    total = 0
    if xmask.any():
        edges += int(np.count_nonzero((dx > 35.0) & xmask))
        total += int(np.count_nonzero(xmask))
    if ymask.any():
        edges += int(np.count_nonzero((dy > 35.0) & ymask))
        total += int(np.count_nonzero(ymask))
    return edges / total if total else 0.0


def canonicalize(label: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
    for prefix in ("a crude drawing of ", "a child s sketch of ", "a simple drawing of "):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value


PROTOTYPES: dict[str, tuple[float, ...]] = {
    "baseball": (0.08, 0.00, 0.00, 0.76, 0.01, 0.13, 0.76, 0.00),
    "apple": (0.64, 0.05, 0.00, 0.04, 0.04, 0.08, 0.63, 0.00),
    "tennis ball": (0.00, 0.47, 0.34, 0.08, 0.00, 0.12, 0.76, 0.00),
    "tomato": (0.72, 0.03, 0.00, 0.02, 0.02, 0.06, 0.72, 0.00),
    "orange": (0.18, 0.00, 0.55, 0.02, 0.01, 0.05, 0.72, 0.00),
    "balloon": (0.32, 0.04, 0.18, 0.12, 0.05, 0.07, 0.68, 0.28),
    "banana": (0.02, 0.00, 0.70, 0.04, 0.04, 0.10, 0.34, 0.00),
    "mug": (0.02, 0.00, 0.00, 0.64, 0.10, 0.18, 0.46, 0.02),
    "book": (0.02, 0.00, 0.08, 0.18, 0.18, 0.28, 0.22, 0.56),
    "car": (0.34, 0.00, 0.02, 0.12, 0.24, 0.30, 0.30, 0.32),
    "chair": (0.10, 0.00, 0.18, 0.10, 0.36, 0.30, 0.28, 0.02),
    "generic": (0.12, 0.12, 0.12, 0.12, 0.04, 0.08, 0.40, 0.12),
}
