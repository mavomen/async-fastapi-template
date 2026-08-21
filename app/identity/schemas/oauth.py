"""OAuth2 / social login Pydantic schemas."""

from pydantic import BaseModel


class OAuthLoginResponse(BaseModel):
    authorize_url: str
    state: str


class OAuthProviderInfo(BaseModel):
    provider: str
    name: str
    authorize_url: str
    enabled: bool
