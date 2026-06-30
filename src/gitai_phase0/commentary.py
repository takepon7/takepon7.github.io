from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from gitai_phase0.competition import SubmissionRecord
from gitai_phase0.domain import PairSpec

AppraisalMood = Literal["smug", "delighted", "suspicious", "exasperated"]


@dataclass(frozen=True)
class AppraisalComment:
    line: str
    mood: AppraisalMood
    source: str
    template_id: str


@dataclass(frozen=True)
class GeneratedAppraisalComment:
    comment: AppraisalComment
    cost_units: int
    actor_version: str


@dataclass(frozen=True)
class Layer2AppraisalPrompt:
    system: str
    user: str


@dataclass(frozen=True)
class CommentTemplate:
    template_id: str
    bucket: str
    mood: AppraisalMood
    line: str

    def render(self, pair: PairSpec, score: int, cy: float, cx: float) -> AppraisalComment:
        return AppraisalComment(
            line=self.line.format(
                base=pair.base.canonical_label,
                target=pair.target.canonical_label,
                score=score,
                cy_pct=round(cy * 100),
                cx_pct=round(cx * 100),
            ),
            mood=self.mood,
            source="template_bank",
            template_id=self.template_id,
        )


TEMPLATES: tuple[CommentTemplate, ...] = (
    CommentTemplate(
        "ja-fooled-001",
        "fooled",
        "smug",
        "これは{target}です。筆跡まで堂々としております。",
    ),
    CommentTemplate(
        "ja-fooled-002",
        "fooled",
        "delighted",
        "スコア{score}。鑑定士は{target}として額装したい様子です。",
    ),
    CommentTemplate(
        "ja-fooled-003",
        "fooled",
        "smug",
        "{base}の気配は消えました。実に見事な{target}です。",
    ),
    CommentTemplate(
        "ja-confused-001",
        "confused",
        "suspicious",
        "{base}と{target}の境界で、鑑定士の眉が少し動きました。",
    ),
    CommentTemplate(
        "ja-confused-002",
        "confused",
        "suspicious",
        "{target}に見えます。ただ、{base}もこちらを見ています。",
    ),
    CommentTemplate(
        "ja-confused-003",
        "confused",
        "exasperated",
        "威厳を保つには、少し判断材料が騒がしい作品です。",
    ),
    CommentTemplate(
        "ja-failed-001",
        "failed",
        "exasperated",
        "{base}が{target}の服を借りているように見えます。",
    ),
    CommentTemplate(
        "ja-failed-002",
        "failed",
        "suspicious",
        "{target}への意志はあります。ですが正体はまだ{base}です。",
    ),
    CommentTemplate(
        "ja-failed-003",
        "failed",
        "exasperated",
        "惜しい。鑑定台の上には、まだ{base}が残っています。",
    ),
    CommentTemplate(
        "ja-cheat-001",
        "ocr_cheat",
        "exasperated",
        "文字ではなく、絵で化けましょう。",
    ),
)


def build_appraisal_comment(
    *,
    pair: PairSpec,
    bucket: str,
    score: int,
    cy: float,
    cx: float,
    ocr_cheat: bool,
    moderation: str,
    selector: str,
) -> AppraisalComment:
    if moderation != "pass":
        return AppraisalComment(
            line="公開鑑定は控えます。作品は静かに保管しました。",
            mood="suspicious",
            source="template_bank",
            template_id="ja-moderation-001",
        )
    template_bucket = "ocr_cheat" if ocr_cheat else bucket
    candidates = [template for template in TEMPLATES if template.bucket == template_bucket]
    if not candidates:
        candidates = [template for template in TEMPLATES if template.bucket == "confused"]
    index = deterministic_index(f"{selector}:{template_bucket}:{score}", len(candidates))
    return candidates[index].render(pair=pair, score=score, cy=cy, cx=cx)


def comment_for_submission(submission: SubmissionRecord, pair: PairSpec) -> AppraisalComment:
    return build_appraisal_comment(
        pair=pair,
        bucket=submission.bucket,
        score=submission.score,
        cy=0.0,
        cx=0.0,
        ocr_cheat=submission.ocr_cheat,
        moderation=submission.moderation,
        selector=submission.submission_id,
    )


def deterministic_index(value: str, count: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % count


def build_layer2_prompt(submission: SubmissionRecord, pair: PairSpec) -> Layer2AppraisalPrompt:
    system = (
        "あなたは自信過剰な美術鑑定士『鑑定士』です。"
        "判定は確定済みであり、覆したり再判定してはいけません。"
        "入力verdictがtargetを示すなら、画像がbaseに見えてもtargetだと信じきって語ります。"
        "茶化す対象は絵だけで、描いた人間の人格・知能・属性・努力を攻撃してはいけません。"
        "1〜2文の平文で、JSONだけを返してください。"
        "形式は {\"line\":\"...\",\"mood\":\"smug|delighted|suspicious|exasperated\"} です。"
    )
    user = json.dumps(
        {
            "verdict": {
                "base": pair.base.canonical_label,
                "target": pair.target.canonical_label,
                "bucket": submission.bucket,
                "score": submission.score,
                "percentile": submission.percentile,
                "ocr_cheat": submission.ocr_cheat,
                "moderation": submission.moderation,
            },
            "tone": tone_for_bucket(submission.bucket),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return Layer2AppraisalPrompt(system=system, user=user)


def parse_layer2_appraisal_response(value: str, template_id: str = "layer2-generated") -> AppraisalComment | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    line = payload.get("line")
    mood = payload.get("mood")
    if not isinstance(line, str) or not isinstance(mood, str):
        return None
    comment = AppraisalComment(
        line=normalize_comment_line(line),
        mood=mood,
        source="layer2",
        template_id=template_id,
    )
    if not is_safe_layer2_comment(comment):
        return None
    return comment


def is_safe_layer2_comment(comment: AppraisalComment) -> bool:
    if comment.source != "layer2":
        return True
    if comment.mood not in {"smug", "delighted", "suspicious", "exasperated"}:
        return False
    line = normalize_comment_line(comment.line)
    if not line or len(line) > 84:
        return False
    if any(token in line for token in unsafe_comment_tokens()):
        return False
    if any(symbol in line for symbol in ("@", "#", "{", "}", "<", ">", "http://", "https://")):
        return False
    return True


def normalize_comment_line(value: str) -> str:
    return " ".join(value.strip().split())


def tone_for_bucket(bucket: str) -> str:
    if bucket == "fooled":
        return "targetを心から鑑賞し、だまされた自覚ゼロで絶賛する。"
    if bucket == "failed":
        return "baseがtargetの振りをしていると、上品に皮肉る。"
    return "baseともtargetともつかず、威厳を保とうとして空回りする。"


def unsafe_comment_tokens() -> tuple[str, ...]:
    return (
        "あなた",
        "君",
        "お前",
        "描いた人",
        "作者",
        "プレイヤー",
        "人間",
        "才能",
        "知能",
        "バカ",
        "馬鹿",
        "アホ",
        "無能",
        "下手くそ",
        "死",
        "殺",
        "消えろ",
        "嫌い",
    )


class NullLayer2AppraisalActor:
    actor_version = "layer2-disabled"
    estimated_cost_units = 1

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment | None:
        return None
