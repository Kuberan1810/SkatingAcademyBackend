from pydantic import BaseModel, EmailStr


class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str | None = None


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str | None
    is_active: bool

    model_config = {
        "from_attributes": True
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"