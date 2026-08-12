from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_admin
from app.models.admin import Admin
from app.schemas.admin import AdminProfileResponse


router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


# =========================================================
# GET ADMIN PROFILE
# =========================================================

@router.get(
    "/profile",
    response_model=AdminProfileResponse,
)
def get_admin_profile(
    current_admin: Admin = Depends(get_current_admin),
):

    return {
        "status": "success",
        "message": "Admin profile fetched successfully",
        "data": {
            "name": current_admin.name,
            "email": current_admin.email,
            "image": getattr(
                current_admin,
                "image",
                None,
            ),
        },
    }