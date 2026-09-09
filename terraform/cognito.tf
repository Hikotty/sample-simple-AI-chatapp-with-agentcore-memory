resource "aws_cognito_user_pool" "main" {
  name = local.name

  # メールアドレスをユーザー名として使う
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = false
  }

  # セルフサインアップは無効。ユーザー作成はアプリのバックエンドが AdminCreateUser で行う
  # （セルフサインアップ有効なプールは社内のセキュリティ自動緩和で強制的に無効化される）
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  tags = { Name = local.name }
}

resource "aws_cognito_user_pool_client" "app" {
  name         = "${local.name}-app"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  id_token_validity      = 12
  access_token_validity  = 12
  refresh_token_validity = 30
  token_validity_units {
    id_token      = "hours"
    access_token  = "hours"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}
