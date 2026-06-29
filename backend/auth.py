from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings


security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify a Supabase JWT token and return the decoded payload.

    Called as a FastAPI dependency on any protected route. Rejects requests
    that carry an invalid, expired, or missing token.

    Args:
        credentials: Bearer token extracted from the Authorization header
            by HTTPBearer.

    Returns:
        dict: Decoded JWT payload containing user_id and other claims.

    Raises:
        HTTPException: 401 if the token is missing, invalid, or expired.
    """
    token = credentials.credentials

    try:
        # Supabase JWTs are signed with the project JWT secret.
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(payload: dict = Depends(verify_token)) -> str:
    """Extract the user ID from a verified JWT payload.

    Used as a dependency on routes that need to scope database queries
    to the authenticated user.

    Args:
        payload: Decoded JWT payload from verify_token.

    Returns:
        str: The user's UUID from the token subject claim.

    Raises:
        HTTPException: 401 if the user ID claim is missing from the token.
    """
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id