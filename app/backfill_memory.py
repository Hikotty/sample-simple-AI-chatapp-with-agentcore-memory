"""既存の会話履歴（RDS）を AgentCore Memory の長期記憶へ一括取り込みする。

短期記憶イベントは作らない。IngestData で各会話をそのまま渡し、抽出だけを任せる。

  actorId   = conversations.user_id（Cognito sub）
  sessionId = conversations.id
  contentTimestamp = その会話の最初のメッセージ時刻

使い方（EC2 上、/etc/memchat.env の環境変数が必要）:
  set -a; . /etc/memchat.env; set +a
  cd /opt/memchat/app && .venv/bin/python backfill_memory.py [--user SUB] [--dry-run]
"""

import argparse
import sys

import db
import memory
from config import settings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", help="特定ユーザー（Cognito sub）だけを対象にする")
    ap.add_argument("--dry-run", action="store_true", help="API を呼ばず件数だけ表示する")
    args = ap.parse_args()

    if not settings.memory_enabled and not args.dry_run:
        print("AGENTCORE_MEMORY_ID が未設定です。/etc/memchat.env を確認してください。", file=sys.stderr)
        return 2

    db.pool.open()
    conversations = calls = skipped = 0
    for conv, msgs in db.iter_user_conversations_with_messages(args.user):
        if not msgs:
            skipped += 1
            continue
        conversations += 1
        first_at = msgs[0]["created_at"]
        print(f"conversation={conv['id']} actor={conv['user_id']} messages={len(msgs)} first_at={first_at.isoformat()}")
        if args.dry_run:
            continue
        calls += memory.ingest_messages(str(conv["user_id"]), str(conv["id"]), msgs, occurred_at=first_at)

    print(f"\ndone: conversations={conversations} skipped(empty)={skipped} ingest_data_calls={calls}"
          f"{' (dry-run)' if args.dry_run else ''}")
    print("長期記憶レコードは非同期に生成されます。数秒〜数分後に list_memory_records で確認してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
