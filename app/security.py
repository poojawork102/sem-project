from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
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

