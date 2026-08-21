from datetime import date
from pydantic import BaseModel, Field, model_validator


class CompensationCreate(BaseModel):
    batch_id: int = Field(gt=0, description="The ID of the batch")
    original_date: date | None = Field(default=None, description="The original class date that was cancelled/missed (optional)")
    compensation_date: date = Field(description="The date when the compensation or extra class will be held")
    reason: str | None = Field(default=None, max_length=255, description="Reason for the compensation or extra class")

    @model_validator(mode="after")
    def validate_dates(self) -> "CompensationCreate":
        if self.original_date is not None and self.original_date == self.compensation_date:
            raise ValueError("compensation_date must be different from original_date")
        return self


class CompensationData(BaseModel):
    id: int
    batch_id: int
    batch_name: str
    original_date: date | None = None
    compensation_date: date
    reason: str | None = None
    status: str

    model_config = {
        "from_attributes": True,
    }



class CompensationResponse(BaseModel):
    status: str
    message: str
    data: CompensationData
