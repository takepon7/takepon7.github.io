from __future__ import annotations

from base64 import b64encode
import json
import os
from typing import Any, Mapping, Protocol, cast
from urllib import error, request

from gitai_phase0.commentary import (
    AppraisalComment,
    AppraisalMood,
    GeneratedAppraisalComment,
    NullLayer2AppraisalActor,
    build_layer2_prompt,
    normalize_comment_line,
)
from gitai_phase0.competition import SubmissionRecord
from gitai_phase0.domain import PairSpec


class HttpOpener(Protocol):
    def __call__(self, req: request.Request, timeout: float):
        raise NotImplementedError


class ScriptedLayer2AppraisalActor:
    actor_version = "scripted-layer2-v1"

    def __init__(
        self,
        line: str,
        mood: str = "smug",
        cost_units: int = 1,
    ) -> None:
        self._line = line
        self._mood = mood
        self.estimated_cost_units = max(1, int(cost_units))

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment:
        return GeneratedAppraisalComment(
            comment=AppraisalComment(
                line=normalize_comment_line(render_scripted_line(self._line, submission, pair)),
                mood=cast(AppraisalMood, self._mood),
                source="layer2",
                template_id="scripted-layer2",
            ),
            cost_units=self.estimated_cost_units,
            actor_version=self.actor_version,
        )


class HttpJsonLayer2AppraisalActor:
    actor_version = "http-json-layer2-v1"

    def __init__(
        self,
        url: str,
        token: str = "",
        timeout_seconds: float = 10.0,
        cost_units: int = 1,
        opener: HttpOpener | None = None,
    ) -> None:
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._opener = opener or request.urlopen
        self.estimated_cost_units = max(1, int(cost_units))

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment | None:
        prompt = build_layer2_prompt(submission, pair)
        payload = {
            "system": prompt.system,
            "user": prompt.user,
            "image_b64": b64encode(image_bytes).decode("ascii"),
        }
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = request.Request(
            self._url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(req, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (OSError, TimeoutError, error.URLError):
            return None

        comment = comment_from_layer2_response_body(body, template_id="http-json-layer2")
        if comment is None:
            return None
        return GeneratedAppraisalComment(
            comment=comment,
            cost_units=self.estimated_cost_units,
            actor_version=self.actor_version,
        )


def build_layer2_actor_from_env(env: Mapping[str, str] | None = None):
    values = os.environ if env is None else env
    actor_kind = values.get("GITAI_LAYER2_ACTOR", "null").strip().lower()
    if actor_kind in {"", "null", "none", "disabled"}:
        return NullLayer2AppraisalActor()
    if actor_kind == "scripted":
        return ScriptedLayer2AppraisalActor(
            line=values.get("GITAI_LAYER2_SCRIPTED_LINE", "これは由緒ある{target}です。"),
            mood=values.get("GITAI_LAYER2_SCRIPTED_MOOD", "smug"),
            cost_units=int(values.get("GITAI_LAYER2_SCRIPTED_COST_UNITS", "1")),
        )
    if actor_kind == "http":
        url = values.get("GITAI_LAYER2_HTTP_URL", "").strip()
        if not url:
            raise ValueError("GITAI_LAYER2_HTTP_URL is required when GITAI_LAYER2_ACTOR=http")
        return HttpJsonLayer2AppraisalActor(
            url=url,
            token=values.get("GITAI_LAYER2_HTTP_TOKEN", ""),
            timeout_seconds=float(values.get("GITAI_LAYER2_HTTP_TIMEOUT", "10")),
            cost_units=int(values.get("GITAI_LAYER2_HTTP_COST_UNITS", "1")),
        )
    raise ValueError(f"Unknown GITAI_LAYER2_ACTOR: {actor_kind}")


def comment_from_layer2_response_body(body: str, template_id: str) -> AppraisalComment | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    return comment_from_layer2_payload(payload, template_id=template_id)


def comment_from_layer2_payload(payload: Any, template_id: str) -> AppraisalComment | None:
    if isinstance(payload, str):
        try:
            return comment_from_layer2_payload(json.loads(payload), template_id=template_id)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    nested = payload.get("comment")
    if isinstance(nested, (dict, str)):
        nested_comment = comment_from_layer2_payload(nested, template_id=template_id)
        if nested_comment is not None:
            return nested_comment
    text = payload.get("text")
    if isinstance(text, str):
        text_comment = comment_from_layer2_payload(text, template_id=template_id)
        if text_comment is not None:
            return text_comment
    line = payload.get("line")
    mood = payload.get("mood")
    if not isinstance(line, str) or not isinstance(mood, str):
        return None
    return AppraisalComment(
        line=normalize_comment_line(line),
        mood=cast(AppraisalMood, mood),
        source="layer2",
        template_id=template_id,
    )


def render_scripted_line(template: str, submission: SubmissionRecord, pair: PairSpec) -> str:
    try:
        return template.format(
            base=pair.base.canonical_label,
            target=pair.target.canonical_label,
            score=submission.score,
            bucket=submission.bucket,
        )
    except (KeyError, ValueError):
        return template
