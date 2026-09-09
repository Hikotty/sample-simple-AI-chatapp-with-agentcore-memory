#!/usr/bin/env bash
# EC2 上で backfill_memory.py を実行し、RDS の既存会話履歴を長期記憶へ取り込む。
#   scripts/run_backfill.sh              … 全ユーザー
#   scripts/run_backfill.sh --dry-run    … 件数確認のみ
#   scripts/run_backfill.sh --user <sub> … 特定ユーザーのみ
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ARGS="$*"
"$DIR/_ssm.sh" "set -a; . /etc/memchat.env; set +a; cd /opt/memchat/app && sudo -u memchat -E .venv/bin/python backfill_memory.py ${ARGS}"
