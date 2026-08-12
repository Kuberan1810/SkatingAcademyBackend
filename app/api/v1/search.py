from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.core.dependencies import get_db

from app.models.admin import Admin

from app.schemas.search import (
    GlobalSearchResponse,
)

from app.services.search_service import (
    global_search,
)


router = APIRouter(
    prefix="/search",
    tags=["Global Search"],
)


# =========================================================
# GLOBAL SEARCH
# =========================================================

@router.get(
    "",
    response_model=GlobalSearchResponse,
)
def search(
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description=(
            "Search students, batches, "
            "payments and sessions"
        ),
    ),

    limit: int = Query(
        20,
        ge=1,
        le=50,
    ),

    db: Session = Depends(get_db),

    current_admin: Admin = Depends(
        get_current_admin
    ),
):

    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty",
        )

    results = global_search(
        db=db,
        query=query,
        limit=limit,
    )

    return {
        "status":
            "success",

        "message":
            "Search results fetched successfully",

        "data": {

            "query":
                query,

            "total":
                len(results),

            "results":
                results,
        },
    }