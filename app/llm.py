"""Amazon Bedrock ConverseStream で Claude Sonnet 5 を呼ぶ。"""

from collections.abc import Iterator

import boto3

from config import settings

_bedrock = boto3.client("bedrock-runtime", region_name=settings.region)

BASE_SYSTEM_PROMPT = (
    "あなたは親切なアシスタントです。ユーザーの言語（既定は日本語）で、簡潔かつ正確に答えてください。"
)

# 直近のこれだけを LLM に渡す（RDS が履歴の正で、ここは文脈窓の制御だけ）
MAX_HISTORY_MESSAGES = 30


def to_converse_messages(history: list[dict]) -> list[dict]:
    """DB の messages（role/content）を Converse API の形式に変換する。"""
    msgs = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in history[-MAX_HISTORY_MESSAGES:]
        if m["content"].strip()
    ]
    # Converse は user から始まり user/assistant が交互である必要がある
    cleaned: list[dict] = []
    for m in msgs:
        if not cleaned and m["role"] != "user":
            continue
        if cleaned and cleaned[-1]["role"] == m["role"]:
            cleaned[-1]["content"][0]["text"] += "\n\n" + m["content"][0]["text"]
        else:
            cleaned.append(m)
    return cleaned


def stream_reply(history: list[dict], system_prompt: str = BASE_SYSTEM_PROMPT) -> Iterator[str]:
    """アシスタント応答をテキスト断片で逐次返す。"""
    resp = _bedrock.converse_stream(
        modelId=settings.bedrock_model_id,
        system=[{"text": system_prompt}],
        messages=to_converse_messages(history),
        # Claude Sonnet 5 は temperature を受け付けない（指定すると ValidationException:
        # "`temperature` is deprecated for this model"）
        inferenceConfig={"maxTokens": 2048},
    )
    for event in resp["stream"]:
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            yield delta["text"]
