from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path

from PIL import Image

from gitai_phase0.domain import PairSpec
from gitai_phase0.puzzle import DailyPuzzle
from gitai_phase0.scoring import percentile_rank
from gitai_phase0.ports import OcrScanner
from gitai_phase0.scoring import normalize_text


@dataclass(frozen=True)
class SeedScoreRef:
    ref_version: str
    pair_id: str
    model_version: str
    template_set_id: str
    tau: float
    scores_sorted: tuple[float, ...]
    stats: dict[str, float]

    @classmethod
    def from_dict(cls, data: dict) -> "SeedScoreRef":
        return cls(
            ref_version=str(data["ref_version"]),
            pair_id=str(data["pair_id"]),
            model_version=str(data["model_version"]),
            template_set_id=str(data["template_set_id"]),
            tau=float(data["tau"]),
            scores_sorted=tuple(float(item) for item in data["scores_sorted"]),
            stats={str(key): float(value) for key, value in data.get("stats", {}).items()},
        )

    def percentile_for(self, raw: float) -> float:
        return percentile_rank(raw, self.scores_sorted)


class PairRepository:
    def __init__(self, path: Path) -> None:
        self._pairs = {
            pair.pair_id: pair
            for pair in (PairSpec.from_dict(item) for item in load_json(path)["pairs"])
        }

    def get(self, pair_id: str) -> PairSpec:
        try:
            return self._pairs[pair_id]
        except KeyError as exc:
            raise KeyError(f"Unknown pair_id: {pair_id}") from exc


class SeedScoreRepository:
    def __init__(self, path: Path) -> None:
        refs = [SeedScoreRef.from_dict(item) for item in load_json(path)["seed_scores"]]
        self._refs = {ref.ref_version: ref for ref in refs}

    def get(self, ref_version: str) -> SeedScoreRef:
        try:
            return self._refs[ref_version]
        except KeyError as exc:
            raise KeyError(f"Unknown ref_version: {ref_version}") from exc

    def list(self) -> list[SeedScoreRef]:
        return list(self._refs.values())

    def find_compatible(self, pair_id: str, model_version: str) -> SeedScoreRef | None:
        candidates = [
            ref
            for ref in self._refs.values()
            if ref.pair_id == pair_id and ref.model_version == model_version
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item.ref_version)[0]


class ImageFingerprintOcrScanner(OcrScanner):
    def __init__(self, path: Path) -> None:
        if path.exists():
            self._fixtures = {
                str(item["fingerprint"]): tuple(str(text) for text in item.get("text", ()))
                for item in load_json(path).get("fixtures", ())
            }
        else:
            self._fixtures = {}

    def scan(self, image: Image.Image, case=None) -> tuple[str, ...]:
        del case
        return self._fixtures.get(image_fingerprint(image), ())


def image_fingerprint(image: Image.Image) -> str:
    import hashlib

    rgba = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(str(rgba.size).encode("ascii"))
    digest.update(rgba.tobytes())
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def guard_text_key(value: str) -> str:
    return normalize_text(value)


class DailyPuzzleRepository:
    def __init__(self, path: Path) -> None:
        payload = load_json(path)
        self._puzzles = [
            DailyPuzzle(
                date=date.fromisoformat(str(item["date"])),
                pair_id=str(item["pair_id"]),
                ref_version=str(item["ref_version"]),
                frozen_at=datetime.fromisoformat(str(item["frozen_at"])),
            )
            for item in payload.get("daily_puzzles", ())
        ]

    def get(self, puzzle_date: date) -> DailyPuzzle:
        for puzzle in self._puzzles:
            if puzzle.date == puzzle_date:
                return puzzle
        raise KeyError(f"Unknown daily puzzle date: {puzzle_date.isoformat()}")

    def current(self, today: date) -> DailyPuzzle:
        eligible = [puzzle for puzzle in self._puzzles if puzzle.date <= today]
        if not eligible:
            raise KeyError(f"No daily puzzle is available on or before: {today.isoformat()}")
        return sorted(eligible, key=lambda item: item.date)[-1]

    def latest(self) -> DailyPuzzle:
        if not self._puzzles:
            raise KeyError("No daily puzzles are available.")
        return sorted(self._puzzles, key=lambda item: item.date)[-1]

    def list(self) -> list[DailyPuzzle]:
        return sorted(self._puzzles, key=lambda item: item.date)

    def available_until(self, today: date) -> list[DailyPuzzle]:
        return [puzzle for puzzle in self.list() if puzzle.date <= today]
