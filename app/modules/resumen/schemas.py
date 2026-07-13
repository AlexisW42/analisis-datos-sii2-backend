from pydantic import BaseModel


class ResumenEjecutivoResponse(BaseModel):
    dataset_id: int
    estado: str
    resumen_ejecutivo_url: str
    message: str
