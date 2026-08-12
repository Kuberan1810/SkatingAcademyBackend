from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: str
    type: str

    title: str
    subtitle: str | None = None
    meta: str | None = None

    image: str | None = None


class SearchResultsData(BaseModel):
    query: str
    total: int

    results: list[SearchResultItem]


class GlobalSearchResponse(BaseModel):
    status: str
    message: str
    data: SearchResultsData