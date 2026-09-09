#!/usr/bin/env bash
# アプリを tar.gz にして S3 へ上げ、EC2 側の update.sh を SSM で実行する。
# 使い方: scripts/deploy.sh   （terraform output を読むので terraform ディレクトリが init 済みであること）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/terraform"
APP_DIR="$ROOT/app"

PROFILE="$(grep -E '^aws_profile' "$TF_DIR/terraform.tfvars" 2>/dev/null | sed -E 's/.*= *"([^"]+)".*/\1/')"
PROFILE="${PROFILE:-default}"
REGION="$(terraform -chdir="$TF_DIR" output -raw region)"
BUCKET="$(terraform -chdir="$TF_DIR" output -raw artifact_bucket)"
INSTANCE_ID="$(terraform -chdir="$TF_DIR" output -raw instance_id)"
export AWS_PROFILE="$PROFILE" AWS_DEFAULT_REGION="$REGION"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# .venv やキャッシュを除いてアーカイブ
tar -czf "$TMP/app.tar.gz" -C "$APP_DIR" \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' .
echo "uploading app.tar.gz ($(du -h "$TMP/app.tar.gz" | cut -f1)) to s3://$BUCKET/"
aws s3 cp "$TMP/app.tar.gz" "s3://$BUCKET/app.tar.gz" --only-show-errors

echo "running /opt/memchat/update.sh on $INSTANCE_ID via SSM"
CMD_ID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "memchat deploy" \
  --parameters 'commands=["/opt/memchat/update.sh"],executionTimeout=["600"]' \
  --query 'Command.CommandId' --output text)"

for _ in $(seq 1 60); do
  STATUS="$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Pending)"
  case "$STATUS" in
    Success) echo "deploy: $STATUS"; break ;;
    Failed|Cancelled|TimedOut) echo "deploy: $STATUS"; aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query '[StandardOutputContent,StandardErrorContent]' --output text | tail -40; exit 1 ;;
    *) sleep 5 ;;
  esac
done
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query StandardOutputContent --output text | tail -15
echo "app url: $(terraform -chdir="$TF_DIR" output -raw app_url)"
