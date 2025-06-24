from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    region: str = "eu-central-1"
    user_pool_id: str
    client_id: str

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

settings = Settings()