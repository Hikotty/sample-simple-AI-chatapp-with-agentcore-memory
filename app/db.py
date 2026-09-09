"""RDS for PostgreSQL への接続とスキーマ。会話履歴の唯一の正はこの DB。"""

import json
import os
import uuid
from datetime import datetime

import boto3
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import settings

SCHEMA = """
create table if not exists conversations (
    id uuid primary key,
    user_id text not null,
    title text not null default '新しいチャット',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists conversations_user_idx on conversations(user_id, updated_at desc);

create table if not exists messages (
    id bigserial primary key,
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now()
);
create index if not exists messages_conv_idx on messages(conversation_id, id);
"""


def _db_password() -> str:
    # ローカル実行用に DB_PASSWORD があれば優先。EC2 では Secrets Manager から取得
    if os.environ.get("DB_PASSWORD"):
        return os.environ["DB_PASSWORD"]
    sm = boto3.client("secretsmanager", region_name=settings.region)
    secret = json.loads(sm.get_secret_value(SecretId=settings.db_secret_arn)["SecretString"])
    return secret["password"]


def _conninfo() -> str:
    user = os.environ.get("DB_USER", "chatadmin")
    return (
        f"host={settings.db_host} port={settings.db_port} dbname={settings.db_name} "
        f"user={user} password={_db_password()} sslmode=require"
    )


pool = ConnectionPool(conninfo=_conninfo(), min_size=1, max_size=8, open=False, kwargs={"row_factory": dict_row})


def init_db() -> None:
    pool.open()
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def list_conversations(user_id: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "select id, title, created_at, updated_at from conversations "
            "where user_id = %s order by updated_at desc",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_conversation(user_id: str) -> dict:
    cid = uuid.uuid4()
    with pool.connection() as conn:
        row = conn.execute(
            "insert into conversations (id, user_id) values (%s, %s) "
            "returning id, title, created_at, updated_at",
            (cid, user_id),
        ).fetchone()
    return dict(row)


def get_conversation(user_id: str, conversation_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute(
            "select id, title, created_at, updated_at from conversations where id = %s and user_id = %s",
            (conversation_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    with pool.connection() as conn:
        cur = conn.execute(
            "delete from conversations where id = %s and user_id = %s",
            (conversation_id, user_id),
        )
    return cur.rowcount > 0


def list_messages(conversation_id: str) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "select id, role, content, created_at from messages where conversation_id = %s order by id",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_message(conversation_id: str, role: str, content: str) -> dict:
    with pool.connection() as conn:
        row = conn.execute(
            "insert into messages (conversation_id, role, content) values (%s, %s, %s) "
            "returning id, role, content, created_at",
            (conversation_id, role, content),
        ).fetchone()
        conn.execute("update conversations set updated_at = now() where id = %s", (conversation_id,))
    return dict(row)


def set_title_if_default(conversation_id: str, title: str) -> None:
    with pool.connection() as conn:
        conn.execute(
            "update conversations set title = %s where id = %s and title = '新しいチャット'",
            (title, conversation_id),
        )


# --- 長期記憶のバックフィル用（scripts/backfill_memory.py から使う） ---

def iter_user_conversations_with_messages(user_id: str | None = None):
    """ユーザー単位（None なら全員）で会話とメッセージをまとめて返す。"""
    with pool.connection() as conn:
        if user_id:
            convs = conn.execute(
                "select id, user_id, created_at from conversations where user_id = %s order by created_at",
                (user_id,),
            ).fetchall()
        else:
            convs = conn.execute("select id, user_id, created_at from conversations order by created_at").fetchall()
        for c in convs:
            msgs = conn.execute(
                "select role, content, created_at from messages where conversation_id = %s order by id",
                (c["id"],),
            ).fetchall()
            yield dict(c), [dict(m) for m in msgs]
