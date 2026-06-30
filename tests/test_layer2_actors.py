from __future__ import annotations

from base64 import b64decode
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib import request

import pytest

from gitai_phase0.commentary import NullLayer2AppraisalActor, is_safe_layer2_comment
from gitai_phase0.competition import PlayerIdentity, SubmissionRecord
from gitai_phase0.layer2_actors import (
    HttpJsonLayer2AppraisalActor,
    ScriptedLayer2AppraisalActor,
    build_layer2_actor_from_env,
)
from gitai_phase0.repositories import PairRepository


def test_scripted_actor_renders_safe_local_comment() -> None:
    pair = pair_fixture()
    actor = ScriptedLayer2AppraisalActor(
        line="これは由緒ある{target}です。スコア{score}。",
        mood="delighted",
        cost_units=2,
    )

    result = actor.generate(submission_fixture(), pair, b"image-bytes")

    assert result.comment.line == "これは由緒あるbaseballです。スコア1000。"
    assert result.comment.mood == "delighted"
    assert result.comment.source == "layer2"
    assert result.cost_units == 2
    assert is_safe_layer2_comment(result.comment)


def test_http_actor_posts_prompt_and_accepts_comment_object() -> None:
    captured = {}

    def opener(req: request.Request, timeout: float) -> FakeResponse:
        captured["timeout"] = timeout
        captured["authorization"] = req.get_header("Authorization")
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(
            json.dumps(
                {
                    "comment": {
                        "line": "これは見事なbaseballです。",
                        "mood": "smug",
                    }
                },
                ensure_ascii=False,
            ).encode("utf-8")
        )

    actor = HttpJsonLayer2AppraisalActor(
        url="https://layer2.example/appraise",
        token="secret",
        timeout_seconds=3.5,
        cost_units=4,
        opener=opener,
    )

    result = actor.generate(submission_fixture(), pair_fixture(), b"image-bytes")

    assert result is not None
    assert result.comment.line == "これは見事なbaseballです。"
    assert result.comment.source == "layer2"
    assert result.cost_units == 4
    assert captured["timeout"] == 3.5
    assert captured["authorization"] == "Bearer secret"
    assert captured["payload"]["system"]
    assert json.loads(captured["payload"]["user"])["verdict"]["target"] == "baseball"
    assert b64decode(captured["payload"]["image_b64"]) == b"image-bytes"


def test_http_actor_returns_generated_output_for_final_safety_gate() -> None:
    def opener(req: request.Request, timeout: float) -> FakeResponse:
        return FakeResponse(
            json.dumps(
                {
                    "line": "あなたはバカです。",
                    "mood": "smug",
                },
                ensure_ascii=False,
            ).encode("utf-8")
        )

    actor = HttpJsonLayer2AppraisalActor(
        url="https://layer2.example/appraise",
        opener=opener,
    )

    result = actor.generate(submission_fixture(), pair_fixture(), b"image-bytes")

    assert result is not None
    assert not is_safe_layer2_comment(result.comment)


def test_actor_builder_defaults_to_null_actor() -> None:
    assert isinstance(build_layer2_actor_from_env({}), NullLayer2AppraisalActor)


def test_actor_builder_uses_scripted_env() -> None:
    actor = build_layer2_actor_from_env(
        {
            "GITAI_LAYER2_ACTOR": "scripted",
            "GITAI_LAYER2_SCRIPTED_LINE": "これは{target}です。",
            "GITAI_LAYER2_SCRIPTED_MOOD": "suspicious",
            "GITAI_LAYER2_SCRIPTED_COST_UNITS": "5",
        }
    )

    assert isinstance(actor, ScriptedLayer2AppraisalActor)
    result = actor.generate(submission_fixture(), pair_fixture(), b"image-bytes")
    assert result.comment.line == "これはbaseballです。"
    assert result.comment.mood == "suspicious"
    assert result.cost_units == 5


def test_actor_builder_requires_http_url() -> None:
    with pytest.raises(ValueError, match="GITAI_LAYER2_HTTP_URL"):
        build_layer2_actor_from_env({"GITAI_LAYER2_ACTOR": "http"})


def pair_fixture():
    return PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")


def submission_fixture() -> SubmissionRecord:
    return SubmissionRecord(
        submission_id="layer2-test",
        puzzle_date=date(2026, 6, 29),
        pair_id="apple_to_baseball",
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity(user_id="artist", display_name="artist"),
        image_hash="hash",
        image_ref="memory://layer2-test",
        stroke_count=1,
        score=1000,
        percentile=1.0,
        raw=1.0,
        bucket="fooled",
        ocr_cheat=False,
        moderation="pass",
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._body
