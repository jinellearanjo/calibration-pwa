import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings loaded from environment variables.
    
    Attributes:
        supabase_url: The Supabase project URL.
        supabase_key: The Supabase service role key.
        supabase_jwt_secret: The Supabase JWT secret for token verification.
        allowed_origins: List of allowed CORS origins.
    """
    
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
    allowed_origins: list = [
        "http://localhost:3000",
    ]

settings = Settings()