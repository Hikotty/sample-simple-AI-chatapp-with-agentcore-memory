#!/usr/bin/env bash
# 共通: EC2 で任意のシェルを SSM 経由で実行し、標準出力を表示する。
#   scripts/_ssm.sh "<command>"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/terraform"
PROFILE="$(grep -E '^aws_profile' "$TF_DIR/terraform.tfvars" 2>/dev/null | sed -E 's/.*= *"([^"]+)".*/\1/')"
export AWS_PROFILE="${PROFILE:-default}"
export AWS_DEFAULT_REGION="$(terraform -chdir="$TF_DIR" output -raw region)"
INSTANCE_ID="$(terraform -chdir="$TF_DIR" output -raw instance_id)"

CMD_JSON="$(python3 -c 'import json,sys; print(json.dumps({"commands":[sys.argv[1]],"executionTimeout":["900"]}))' "$1")"
CMD_ID="$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
  --parameters "$CMD_JSON" --query 'Command.CommandId' --output text)"

for _ in $(seq 1 180); do
  STATUS="$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Pending)"
  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut) break ;;
    *) sleep 5 ;;
  esac
done
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text
[ "$STATUS" = "Success" ] || { echo "ssm status: $STATUS" >&2; exit 1; }
