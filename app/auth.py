"""Cognito 認証。Hosted UI を使わず、バックエンドが USER_PASSWORD_AUTH を代行する。

ブラウザは ID トークンを受け取り、以降 Authorization: Bearer で送る。
バックエンドは JWKS で署名を検証し、`sub` をユーザー ID として使う。
この `sub` が後で AgentCore Memory の actorId になる。
"""

from dataclasses import dataclass

import boto3
import jwt
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

from config import settings

_idp = boto3.client("cognito-idp", region_name=settings.region)
_jwks = PyJWKClient(f"{settings.cognito_issuer}/.well-known/jwks.json", cache_keys=True)


@dataclass(frozen=True)
class User:
    sub: str
    email: str


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(status_code=status_code, detail=detail)


def signup(email: str, password: str) -> None:
    """管理 API でユーザーを作成する（セルフサインアップは使わない）。

    ユーザープールは AllowAdminCreateUserOnly=true。アプリのバックエンドが
    AdminCreateUser + AdminSetUserPassword(Permanent) で確認済みユーザーを作る。
    """
    try:
        _idp.admin_create_user(
            UserPoolId=settings.cognito_user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",  # 招待メールを送らない
        )
        _idp.admin_set_user_password(
            UserPoolId=settings.cognito_user_pool_id,
            Username=email,
            Password=password,
            Permanent=True,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UsernameExistsException":
            raise AuthError("このメールアドレスは既に登録されています", 409)
        if code == "InvalidPasswordException":
            raise AuthError("パスワードは 8 文字以上で英小文字と数字を含めてください", 400)
        raise AuthError(f"サインアップに失敗しました: {code}", 400)


def login(email: str, password: str) -> dict:
    try:
        resp = _idp.initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise AuthError("メールアドレスまたはパスワードが正しくありません")
        raise AuthError(f"ログインに失敗しました: {code}", 400)
    result = resp["AuthenticationResult"]
    return {"id_token": result["IdToken"], "expires_in": result["ExpiresIn"]}


def verify_id_token(token: str) -> User:
    try:
        signing_key = _jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
        )
    except jwt.PyJWTError as e:
        raise AuthError(f"トークンが無効です: {e.__class__.__name__}")
    if claims.get("token_use") != "id":
        raise AuthError("ID トークンではありません")
    return User(sub=claims["sub"], email=claims.get("email", ""))


def current_user(request: Request) -> User:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise AuthError("認証が必要です")
    return verify_id_token(header.split(" ", 1)[1].strip())


CurrentUser = Depends(current_user)
