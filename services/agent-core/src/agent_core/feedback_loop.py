"""差戻フィードバック取込(E5-8、FR-AU-03)。

E3-6で承認が差し戻された(`Approval.decision == "rejected"`)場合、
(1) 差し戻し理由(`reason`)を該当業務グラフの「次回起案」プロンプトへ
コンテキストとして注入するためのメッセージを組み立て、
(2) 差し戻しペア(元の起案内容+差し戻し理由+ある場合は修正版)を
`feedback_queue/`へJSONL形式でキューイングする(E8-5の学習データ取込の
入力となる、選好ペア候補)。

差し戻し検知そのもの(E3-10のWebSocketイベント購読、またはポーリング)は
呼び出し側(業務グラフ・チャットランナー等)の責務とし、本モジュールは
「rejectedなapprovalが渡された場合にどう処理するか」のみを提供する
(疎結合: 本モジュールはWebSocket接続を持たない)。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

Message = dict[str, str]


@dataclass
class FeedbackRecord:
    """差し戻しペア(選好ペア候補、E8-5の学習データ取込の入力)1件分。"""

    approval_id: str
    target: str
    original_draft: dict[str, Any]
    reason: str
    revised_draft: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_rejection_context_message(approval: dict[str, Any]) -> Message:
    """差し戻し理由を次回起案プロンプトへ注入するためのメッセージを組み立てる。

    LLMへの`messages`リストにそのまま追加できる`{"role": "user", ...}`
    形式で返す。
    """
    target = approval.get("target", "")
    reason = approval.get("reason", "")
    content = (
        f"前回の起案(対象: {target})は差し戻されました。差し戻し理由: {reason}\n"
        "この理由を踏まえて改善した案を再度提示してください。"
    )
    return {"role": "user", "content": content}


def enqueue_feedback(record: FeedbackRecord, *, queue_dir: Path) -> Path:
    """差し戻しペアを`queue_dir`配下のJSONLファイルへ追記する。

    ファイルは`queue_dir`内に日付単位(`YYYY-MM-DD.jsonl`)で作成し、
    複数の差し戻しは同一ファイルへ追記され続ける(E8-5が一括読取できる
    よう、ファイル数を無闇に増やさない設計)。
    """
    queue_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    path = queue_dir / f"{today}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


async def on_rejection(
    approval: dict[str, Any],
    *,
    queue_dir: Path,
    original_draft: dict[str, Any] | None = None,
    revised_draft: dict[str, Any] | None = None,
) -> Message | None:
    """差し戻されたapprovalを検知した際の共通処理。

    `approval["decision"]`が`"rejected"`でない場合は何もせず`None`を返す
    (呼び出し側は承認・却下いずれの通知でも安全に本関数を呼べる)。
    rejectedの場合、差し戻しペアを`feedback_queue/`へ記録し、次回起案時に
    LLMコンテキストへ注入すべきメッセージを返す。
    """
    if approval.get("decision") != "rejected":
        return None

    record = FeedbackRecord(
        approval_id=str(approval.get("id", uuid4())),
        target=str(approval.get("target", "")),
        original_draft=original_draft or {},
        reason=str(approval.get("reason", "")),
        revised_draft=revised_draft,
    )
    enqueue_feedback(record, queue_dir=queue_dir)

    return build_rejection_context_message(approval)


__all__ = [
    "FeedbackRecord",
    "Message",
    "build_rejection_context_message",
    "enqueue_feedback",
    "on_rejection",
]
