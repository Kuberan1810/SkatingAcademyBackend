from pydantic import BaseModel


class AdminProfileData(BaseModel):
    name: str
    email: str
    image: str | None = None


class AdminProfileResponse(BaseModel):
    status: str
    message: str
    data: AdminProfileData