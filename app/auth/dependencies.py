from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.core.dependencies import get_db
from app.models.admin import Admin


# Swagger / FastAPI Bearer authentication
security = HTTPBearer()


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:

    # Get JWT token from:
    # Authorization: Bearer <token>
    token = credentials.credentials

    # Decode and validate JWT
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # Get admin ID from JWT "sub"
    admin_id = payload.get("sub")

    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # Convert admin ID from string to integer
    try:
        admin_id = int(admin_id)

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # Find active admin in database
    admin = (
        db.query(Admin)
        .filter(
            Admin.id == admin_id,
            Admin.is_active.is_(True),
        )
        .first()
    )

    # Admin doesn't exist / inactive
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found or inactive",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # Return authenticated admin
    return admin