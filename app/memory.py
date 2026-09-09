"""AgentCore Memory の長期記憶統合。

短期記憶（イベント）は作らない。会話履歴は RDS が持ち続け、
AgentCore Memory には IngestData で「抽出だけ」を任せる。

- actorId  = Cognito の sub（ユーザー識別子）
- sessionId = conversations.id（会話単位で関連コンテキストとして扱わせる）
- namespace 前提: メモリのストラテジーが `/users/{actorId}/...` のテンプレートで作られていること

AGENTCORE_MEMORY_ID が未設定なら、すべて no-op になる。
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from config import settings

log = logging.getLogger("memchat.memory")

NAMESPACE_PREFIX = os.environ.get("MEMORY_NAMESPACE_PREFIX", "/users/{actorId}/")
RETRIEVE_TOP_K = int(os.environ.get("MEMORY_TOP_K", "8"))
INGEST_BATCH = 100  # IngestData の payload 上限

_client = boto3.client("bedrock-agentcore", region_name=settings.region) if settings.memory_enabled else None


def _namespace(actor_id: str) -> str:
    return NAMESPACE_PREFIX.replace("{actorId}", actor_id)


def _to_payload(messages: list[dict]) -> list[dict]:
    role_map = {"user": "USER", "assistant": "ASSISTANT"}
    return [
        {"conversational": {"role": role_map[m["role"]], "content": {"text": m["content"]}}}
        for m in messages
        if m["content"].strip()
    ]


def ingest_messages(actor_id: str, session_id: str, messages: list[dict], occurred_at: datetime | None = None) -> int:
    """会話メッセージを長期記憶へ直接取り込む（短期イベントは作らない）。

    100 件ずつに分割して IngestData を呼ぶ。戻り値は呼び出した回数。
    """
    if _client is None or not messages:
        return 0
    payload = _to_payload(messages)
    calls = 0
    for i in range(0, len(payload), INGEST_BATCH):
        chunk = payload[i : i + INGEST_BATCH]
        _client.ingest_data(
            memoryId=settings.agentcore_memory_id,
            actorId=actor_id,
            sessionId=session_id,
            contentTimestamp=occurred_at or datetime.now(timezone.utc),
            source={"inline": {"payload": chunk}},
        )
        calls += 1
    return calls


def ingest_turn_safely(actor_id: str, session_id: str, user_text: str, assistant_text: str) -> None:
    """1 ターン（user + assistant）を取り込む。失敗しても会話体験は止めない。"""
    if _client is None:
        return
    try:
        ingest_messages(
            actor_id,
            session_id,
            [{"role": "user", "content": user_text}, {"role": "assistant", "content": assistant_text}],
        )
    except Exception:  # noqa: BLE001
        log.exception("IngestData failed (actor=%s session=%s)", actor_id, session_id)


def retrieve_context(actor_id: str, query: str) -> list[str]:
    """ユーザーの長期記憶をセマンティック検索して本文のリストを返す。"""
    if _client is None or not query.strip():
        return []
    try:
        resp = _client.retrieve_memory_records(
            memoryId=settings.agentcore_memory_id,
            # 階層取得は namespacePath。/users/{sub}/ 配下の preferences/ と facts/ をまとめて検索する。
            # （2026-09 時点の実測では namespace パラメータは完全一致で、配下のレコードは返らなかった）
            namespacePath=_namespace(actor_id),
            searchCriteria={"searchQuery": query[:10000], "topK": RETRIEVE_TOP_K},
        )
    except Exception:  # noqa: BLE001
        log.exception("RetrieveMemoryRecords failed (actor=%s)", actor_id)
        return []
    texts = []
    for rec in resp.get("memoryRecordSummaries", []):
        text = _record_text(rec.get("content", {}).get("text", ""))
        if text:
            texts.append(text)
    return texts


def _record_text(raw: str) -> str:
    """USER_PREFERENCE ストラテジーのレコードは JSON 文字列（context/preference/categories）で返るので、
    プロンプトに入れやすい 1 行に整える。SEMANTIC のレコードはそのままの文。"""
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and obj.get("preference"):
                ctx = obj.get("context")
                return f"{obj['preference']}（{ctx}）" if ctx else str(obj["preference"])
        except json.JSONDecodeError:
            pass
    return raw


def build_system_prompt(base: str, memories: list[str]) -> str:
    """長期記憶を system prompt に注入する。"""
    if not memories:
        return base
    bullets = "\n".join(f"- {m}" for m in memories)
    return (
        f"{base}\n\n"
        "以下は、このユーザーとの過去の会話から抽出された長期記憶です。"
        "関連する場合だけ自然に活かし、記憶の存在を不必要に言及しないでください。\n"
        f"{bullets}"
    )
