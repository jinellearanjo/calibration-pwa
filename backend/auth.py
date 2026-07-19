import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import settings
import database

security = HTTPBearer()

_jwks_cache: dict | None = None
JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

# Maps a user's real job title (profiles.title) to a permission tier. Kept
# here in one place rather than duplicated as a DB CHECK constraint, so
# changing what a title can do doesn't require a migration. profiles.title
# itself still has a CHECK constraint listing the known titles, to catch
# typos at the database level - update both together if a new title is
# ever added.
#
# "full_edit": QM/TM/MR/MD - everything, including approving/rejecting
#   flagged reports and role-change requests.
# "cert_creation": Cal Tech/Engineer/Admin/Lab Staff - can create
#   instruments/sessions, enter readings, generate certificates (subject
#   to the review workflow for flagged sessions), but not approve anything.
# "read_only": Viewer - view only, can submit a role-change request.
TITLE_PERMISSION_TIER = {
    "QM": "full_edit",
    "TM": "full_edit",
    "MR": "full_edit",
    "MD": "full_edit",
    "Cal Tech": "cert_creation",
    "Engineer": "cert_creation",
    "Admin": "cert_creation",
    "Lab Staff": "cert_creation",
    "Viewer": "read_only",
}


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


def get_current_user_title(user_id: str = Depends(get_current_user_id)) -> str:
    """Look up the current user's real job title from their profile.

    A missing profile (shouldn't happen in practice, since one is created
    automatically on sign-up by the handle_new_user trigger - see the
    2026-07-19 migration - but could occur for an account created before
    that migration ran) defaults to "Viewer", the safest fallback.

    Args:
        user_id: The authenticated user's ID, from get_current_user_id.

    Returns:
        str: The user's job title (e.g. "QM", "Cal Tech", "Viewer").
    """
    profile = database.get_profile(user_id)
    if profile is None:
        return "Viewer"
    return profile.get("title", "Viewer")


def require_tier(*allowed_tiers: str):
    """FastAPI dependency factory: only allow users whose permission tier
    (derived from their job title via TITLE_PERMISSION_TIER) is one of
    allowed_tiers.

    Usage: `user_id: str = Depends(require_tier("full_edit", "cert_creation"))`
    - this both enforces the check AND gives you the caller's user_id in
    one dependency, matching how get_current_user_id is used elsewhere.

    Args:
        *allowed_tiers: One or more permission tiers that may proceed
            ("full_edit", "cert_creation", "read_only").

    Returns:
        A dependency function that returns the caller's user_id if their
        tier is allowed, or raises 403 otherwise.
    """
    def _check(
        user_id: str = Depends(get_current_user_id),
        title: str = Depends(get_current_user_title),
    ) -> str:
        tier = TITLE_PERMISSION_TIER.get(title, "read_only")
        if tier not in allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ({title}) doesn't have permission to do this.",
            )
        return user_id
    return _check