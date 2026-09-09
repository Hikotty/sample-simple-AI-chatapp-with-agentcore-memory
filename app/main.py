"""memchat: 会話を分けられる最小の ChatGPT ライクなチャットアプリ。

FastAPI + RDS(PostgreSQL) + Bedrock(Claude Sonnet 5) + Cognito。
長期記憶（AgentCore Memory）は memory.py に隔離してあり、AGENTCORE_MEMORY_ID が
未設定なら一切呼ばれない。
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

import auth
import db
import llm
import memory
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("memchat")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    log.info("memory integration: %s", "enabled" if settings.memory_enabled else "disabled")
    yield
    db.pool.close()


app = FastAPI(title="memchat", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
@app.get("/api/healthz")  # CloudFront 経由では /api/* だけが EC2 に届く
def healthz():
    return {"ok": True, "memory": settings.memory_enabled, "model": settings.bedrock_model_id}


# ---------- 認証 ----------

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


@app.post("/api/auth/signup", status_code=201)
def api_signup(body: Credentials):
    auth.signup(body.email, body.password)
    return {"ok": True}


@app.post("/api/auth/login")
def api_login(body: Credentials):
    return auth.login(body.email, body.password)


@app.get("/api/me")
def api_me(user: auth.User = auth.CurrentUser):
    return {"sub": user.sub, "email": user.email, "memory_enabled": settings.memory_enabled}


# ---------- 会話 ----------

@app.get("/api/conversations")
def api_list_conversations(user: auth.User = auth.CurrentUser):
    return db.list_conversations(user.sub)


@app.post("/api/conversations", status_code=201)
def api_create_conversation(user: auth.User = auth.CurrentUser):
    return db.create_conversation(user.sub)


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def api_delete_conversation(conversation_id: str, user: auth.User = auth.CurrentUser):
    if not db.delete_conversation(user.sub, conversation_id):
        raise HTTPException(404, "conversation not found")


@app.get("/api/conversations/{conversation_id}/messages")
def api_list_messages(conversation_id: str, user: auth.User = auth.CurrentUser):
    if not db.get_conversation(user.sub, conversation_id):
        raise HTTPException(404, "conversation not found")
    return db.list_messages(conversation_id)


class NewMessage(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@app.post("/api/conversations/{conversation_id}/messages")
def api_send_message(conversation_id: str, body: NewMessage, user: auth.User = auth.CurrentUser):
    if not db.get_conversation(user.sub, conversation_id):
        raise HTTPException(404, "conversation not found")

    user_text = body.content.strip()
    db.add_message(conversation_id, "user", user_text)
    db.set_title_if_default(conversation_id, user_text[:30])
    history = db.list_messages(conversation_id)

    # 長期記憶: 過去の会話から抽出された記憶を system prompt に注入（メモリ無効時は no-op）
    memories = memory.retrieve_context(user.sub, user_text)
    system_prompt = memory.build_system_prompt(llm.BASE_SYSTEM_PROMPT, memories)

    def event_stream():
        parts: list[str] = []
        try:
            if memories:
                yield _sse({"type": "memory", "count": len(memories), "items": memories})
            for chunk in llm.stream_reply(history, system_prompt):
                parts.append(chunk)
                yield _sse({"type": "token", "text": chunk})
        except Exception as e:  # noqa: BLE001
            log.exception("bedrock stream failed")
            yield _sse({"type": "error", "message": f"モデル呼び出しに失敗しました: {e.__class__.__name__}"})
            return
        assistant_text = "".join(parts)
        saved = db.add_message(conversation_id, "assistant", assistant_text)
        # 長期記憶: このターンを直接取り込む（短期イベントは作らない。無効時は no-op）
        memory.ingest_turn_safely(user.sub, conversation_id, user_text, assistant_text)
        yield _sse({"type": "done", "message": {"id": saved["id"], "role": "assistant", "content": assistant_text}})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
