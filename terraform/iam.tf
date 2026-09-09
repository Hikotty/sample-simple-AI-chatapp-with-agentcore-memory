data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-app"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# SSM Session Manager（SSH 鍵なしで操作）
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app" {
  # アプリ配布物の取得
  statement {
    sid       = "ReadArtifacts"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
  }

  # RDS マスターパスワード（Secrets Manager 管理）
  statement {
    sid       = "ReadDbSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.main.master_user_secret[0].secret_arn]
  }

  # Bedrock: 推論プロファイル + 配下の基盤モデル（クロスリージョン分も含む）
  statement {
    sid = "InvokeBedrock"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.bedrock_model_id}",
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-5*",
    ]
  }

  # Cognito: 管理 API によるユーザー作成（InitiateAuth 自体は認証不要 API）
  statement {
    sid = "CognitoAdmin"
    actions = [
      "cognito-idp:AdminCreateUser",
      "cognito-idp:AdminSetUserPassword",
      "cognito-idp:AdminGetUser",
    ]
    resources = [aws_cognito_user_pool.main.arn]
  }

  # AgentCore Memory: 長期記憶への直接取り込みと取得（後で有効化するため先に付与）
  statement {
    sid = "AgentCoreMemory"
    actions = [
      "bedrock-agentcore:IngestData",
      "bedrock-agentcore:RetrieveMemoryRecords",
      "bedrock-agentcore:ListMemoryRecords",
      "bedrock-agentcore:GetMemory",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${var.region}:${data.aws_caller_identity.current.account_id}:memory/*",
    ]
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "${local.name}-app"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-app"
  role = aws_iam_role.app.name
}
