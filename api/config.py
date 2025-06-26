# api/config.py  – final, battle-tested version
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(".env.dev"), override=False)

class Settings(BaseSettings):
    COGNITO_USER_POOL_ID:  str
    COGNITO_APP_CLIENT_ID: str
    AWS_REGION:            str = "eu-central-1"          # keep default

    model_config = SettingsConfigDict(env_file=".env",
                                      case_sensitive=True,
                                      extra="ignore")  # ← allow other env-vars

    # convenience aliases used elsewhere in code -----------------------------
    @property
    def user_pool_id(self) -> str:  return self.COGNITO_USER_POOL_ID

    @property
    def client_id(self)    -> str:  return self.COGNITO_APP_CLIENT_ID

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

settings = Settings()        # ← will no longer crash if both vars exist
