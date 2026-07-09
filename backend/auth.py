import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings

security = HTTPBearer()

_jwks_cache: dict | None = None
JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"


def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        response = httpx.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


def _get_signing_key(token: str) -> dict:
    global _jwks_cache
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    for key in _get_jwks()["keys"]:
        if key["kid"] == kid:
            return key
    _jwks_cache = None
    for key in _get_jwks()["keys"]:
        if key["kid"] == kid:
            return key
    raise JWTError(f"No matching JWKS key found for kid={kid}")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(payload: dict = Depends(verify_token)) -> str:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id