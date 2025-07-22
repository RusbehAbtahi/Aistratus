# api/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv
import os
from tinyllama.utils.ssm import get_id

# Load local .env.dev if present, but we’ll override with SSM below
load_dotenv(find_dotenv(".env.dev"), override=False)

class Settings(BaseSettings):
    COGNITO_USER_POOL_ID:  str
    COGNITO_CLIENT_ID: str
    AWS_REGION:            str = "eu-central-1"  # default region

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # allow other env-vars
    )

    # convenience aliases used elsewhere in code
    @property
    def user_pool_id(self) -> str:
        return self.COGNITO_USER_POOL_ID

    @property
    def client_id(self) -> str:
        return self.COGNITO_CLIENT_ID

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

# Instantiate from any .env, then override from SSM Parameter Store
settings = Settings()

# ── Override with values stored under /tinyllama/<env>/… ──
settings.COGNITO_USER_POOL_ID  = get_id("cognito_user_pool_id")
settings.COGNITO_CLIENT_ID = get_id("cognito_client_id")
