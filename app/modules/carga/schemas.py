from datetime import datetime
from typing import Any

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
    resumen_ejecutivo_disponible: bool = False
    resumen_ejecutivo_url: str | None = None

    class Config:
        from_attributes = True


class DatasetContenidoResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    nombre_archivo: str | None = None
    formato: str
    total_filas: int
    total_columnas: int
    current_page: int
    number_of_records: int
    total_pages: int
    has_previous_page: bool
    has_next_page: bool
    columnas: list[str]
    filas: list[dict[str, Any]]
    resumen_ejecutivo_disponible: bool = False
    resumen_ejecutivo_url: str | None = None
