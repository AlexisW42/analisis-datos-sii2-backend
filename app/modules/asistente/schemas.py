from pydantic import BaseModel, Field


class AsistentePreguntaRequest(BaseModel):
    dataset_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1, max_length=1000)


class AsistentePreguntaResponse(BaseModel):
    dataset_id: int
    question: str
    answer: str
    model: str
