#!/usr/bin/env bash
# 実行中の EC2 の AGENTCORE_MEMORY_ID を書き換えてアプリを再起動する（インスタンス再作成なし）。
#   scripts/set_memory_id.sh <memory-id>   … 長期記憶統合を有効化
#   scripts/set_memory_id.sh ""            … 無効化（Before の状態に戻す）
# 恒久化したい場合は terraform.tfvars の agentcore_memory_id にも同じ値を入れる
# （user_data が変わるため apply でインスタンスは再作成される。履歴は RDS にあるので失われない）。
set -euo pipefail
MEMORY_ID="${1-}"
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/_ssm.sh" "sed -i 's|^AGENTCORE_MEMORY_ID=.*|AGENTCORE_MEMORY_ID=${MEMORY_ID}|' /etc/memchat.env && systemctl restart memchat && sleep 3 && grep AGENTCORE_MEMORY_ID /etc/memchat.env && curl -s http://localhost/healthz"
