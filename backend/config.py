import os
from dotenv import load_dotenv

load_dotenv()

def _parse_allowed_origins() -> list:
    """Build the CORS allow-list from the ALLOWED_ORIGINS env var.

    ALLOWED_ORIGINS should be a comma-separated list of full origins
    (scheme + host, no path), e.g.:
        ALLOWED_ORIGINS=https://calibration-pwa.vercel.app,https://calibration-pwa-git-main.vercel.app

    http://localhost:3000 is always included so local dev keeps working
    regardless of what's set in production. Empty/whitespace-only entries
    are dropped.
    """
    extra = os.getenv("ALLOWED_ORIGINS", "")
    origins = ["http://localhost:3000"]
    origins += [o.strip() for o in extra.split(",") if o.strip()]
    return origins

class Settings:
    """Application settings loaded from environment variables.
    
    Attributes:
        supabase_url: The Supabase project URL.
        supabase_key: The Supabase service role key.
        supabase_jwt_secret: The Supabase JWT secret for token verification.
        allowed_origins: List of allowed CORS origins. Always includes
            localhost:3000 for local dev; add production origins via the
            ALLOWED_ORIGINS env var (comma-separated).
    """
    
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
    allowed_origins: list = _parse_allowed_origins()

settings = Settings()