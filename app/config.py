"""環境変数から設定を読む。EC2 では /etc/memchat.env が systemd 経由で注入される。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    region: str
    cognito_user_pool_id: str
    cognito_client_id: str
    db_secret_arn: str
    db_host: str
    db_port: int
    db_name: str
    bedrock_model_id: str
    agentcore_memory_id: str  # 空文字なら長期記憶統合は無効

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.cognito_user_pool_id}"

    @property
    def memory_enabled(self) -> bool:
        return bool(self.agentcore_memory_id)


def load_settings() -> Settings:
    return Settings(
        region=os.environ.get("AWS_REGION", "us-east-1"),
        cognito_user_pool_id=os.environ["COGNITO_USER_POOL_ID"],
        cognito_client_id=os.environ["COGNITO_CLIENT_ID"],
        db_secret_arn=os.environ.get("DB_SECRET_ARN", ""),
        db_host=os.environ["DB_HOST"],
        db_port=int(os.environ.get("DB_PORT", "5432")),
        db_name=os.environ.get("DB_NAME", "chat"),
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-5"),
        agentcore_memory_id=os.environ.get("AGENTCORE_MEMORY_ID", "").strip(),
    )


settings = load_settings()
