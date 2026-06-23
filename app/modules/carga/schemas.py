from datetime import datetime
from pydantic import BaseModel

class CargaResponse(BaseModel):
    message: str

class DatasetResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    nombre_archivo: str | None = None
    peso_bytes: int
    fecha_subida: datetime
    formato: str
    estado: str = "Disponible"

    class Config:
        from_attributes = True
