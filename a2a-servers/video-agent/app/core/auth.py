"""Authentication utilities for A2A Video Agent."""

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

security = HTTPBearer()


async def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """
    Verify Bearer token authentication.

    Args:
        credentials: HTTP Authorization credentials from request header

    Returns:
        The validated token string

    Raises:
        HTTPException: If token is invalid or missing
    """
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication scheme. Expected 'Bearer'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
