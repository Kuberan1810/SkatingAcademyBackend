from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.auth.jwt import create_access_token
from app.auth.security import hash_password, verify_password
from app.core.dependencies import get_db
from app.models.admin import Admin
from app.schemas.auth import (
    AdminCreate,
    AdminLogin,
    AdminResponse,
    TokenResponse,
)

from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=AdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_admin(
    data: AdminCreate,
    db: Session = Depends(get_db),
):
    existing_admin = (
        db.query(Admin)
        .filter(Admin.email == data.email)
        .first()
    )

    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists",
        )

    admin = Admin(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        phone=data.phone,
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    return admin


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_admin(
    data: AdminLogin,
    db: Session = Depends(get_db),
):
    admin = (
        db.query(Admin)
        .filter(Admin.email == data.email)
        .first()
    )

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    if not verify_password(
        data.password,
        admin.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive",
        )

    access_token = create_access_token(
        {
            "sub": str(admin.id),
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=AdminResponse,
)
def get_me(
    current_admin: Admin = Depends(get_current_admin),
):
    return current_admin