import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


def _auth_configuration() -> tuple[str, set[str]]:
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    parsed_url = urlsplit(supabase_url)
    local_http = (
        parsed_url.scheme == "http"
        and parsed_url.hostname in ("localhost", "127.0.0.1")
    )
    if (
        not parsed_url.hostname
        or (parsed_url.scheme != "https" and not local_http)
        or parsed_url.username
        or parsed_url.password
        or parsed_url.path
        or parsed_url.query
        or parsed_url.fragment
    ):
        logger.error("Authentication configuration rejected: invalid_supabase_url")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    allowed_user_ids = {
        user_id.strip().lower()
        for user_id in os.getenv("SAASSPEND_ALLOWED_USER_IDS", "").split(",")
        if user_id.strip()
    }
    if not allowed_user_ids:
        logger.error("Authentication configuration rejected: empty_user_allowlist")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API access is not configured",
        )
    return supabase_url, allowed_user_ids


@lru_cache(maxsize=8)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(
        f"{supabase_url}/auth/v1/.well-known/jwks.json",
        timeout=5,
    )


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Authentication rejected: missing_bearer_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_url, allowed_user_ids = _auth_configuration()
    issuer = f"{supabase_url}/auth/v1"
    try:
        signing_key = _jwks_client(supabase_url).get_signing_key_from_jwt(
            credentials.credentials
        )
    except PyJWKClientConnectionError as error:
        logger.warning("Authentication failed: jwks_service_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from error
    except PyJWKClientError as error:
        logger.warning(
            "Authentication rejected: signing_key_lookup_failed error_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except PyJWTError as error:
        logger.warning(
            "Authentication rejected: token_parse_failed error_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except PyJWTError as error:
        logger.warning(
            "Authentication rejected: token_claim_validation_failed error_type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        logger.warning("Authentication rejected: invalid_subject_claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if subject.lower() not in allowed_user_ids:
        logger.warning(
            "Authentication rejected: user_not_allowlisted allowlist_entries=%d",
            len(allowed_user_ids),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized",
        )
    return AuthenticatedUser(user_id=subject)
