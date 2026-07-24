"""Central settings. The reference project read os.environ ad hoc; a single
pydantic-settings class is the one deliberate upgrade (see docs/PATTERNS.md)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_version: str = "0.1.0"

    # Postgres (Neon). Accepts postgres:// or postgresql:// and is normalised
    # to the psycopg3 dialect by db.py. Use the DIRECT Neon endpoint, not the
    # -pooler one (pooled reads served stale data in the reference project).
    database_url: str = ""

    # Clerk JWT verification (RS256 against the issuer's JWKS).
    clerk_jwt_issuer: str = ""
    clerk_audience: str = ""
    # "1" skips JWT verification entirely. Local dev only.
    clerk_auth_disabled: bool = False

    # Comma-separated Clerk user IDs allowed to hit /admin/* endpoints.
    admin_clerk_user_ids: str = ""

    # Comma-separated origins allowed to call the API.
    cors_allowed_origins: str = "http://localhost:3000"

    # Shared secret for HMAC-signed internal endpoints (marker Lambda,
    # generation writer Lambda). Unset = internal endpoints refuse requests.
    internal_hmac_secret: str = ""
    internal_hmac_max_skew_seconds: int = 300

    # Photo upload bucket (created by the CDK UploadPipelineStack).
    s3_upload_bucket: str = ""
    aws_region: str = "ap-southeast-1"
    upload_url_ttl_seconds: int = 300

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def admin_user_ids(self) -> set[str]:
        return {u.strip() for u in self.admin_clerk_user_ids.split(",") if u.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
