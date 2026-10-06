import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from .config import settings

scheme = HTTPBearer()
ALGORITHM = "HS256"


def create_access_token(subject: str) -> str:
    return jwt.encode({"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, settings.jwt_secret, algorithm=ALGORITHM)


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(scheme)) -> str:
    try:
        data = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
        if data.get("sub") != settings.admin_username:
            raise JWTError()
        return data["sub"]
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid admin token required") from exc


def require_submissions_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Gates /v1/submissions. Fails closed: an unconfigured key disables the endpoint
    rather than leaving it open, and the comparison is constant-time to avoid leaking
    the key length/prefix through response timing."""
    if not settings.submissions_api_key or not x_api_key or not secrets.compare_digest(x_api_key, settings.submissions_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid X-API-Key header required")
    return x_api_key

