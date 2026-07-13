from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PivotRequest(BaseModel):
    dataset_id: int
    filas: List[str] = Field(..., description="Lista de variables para agrupar en las filas")
    columnas: List[str] = Field(default=[], description="Lista de variables para agrupar en las columnas")
    valores: str = Field(..., description="La variable numérica o categórica a medir")
    funcion_agregacion: str = Field(
        ..., 
        description="Operación matemática: 'sum', 'mean', 'count', 'max', 'min'"
    )

class PivotResponse(BaseModel):
    dataset_id: int
    configuracion: dict
    # Entregamos la tabla como un diccionario orientado a registros, ideal para el Frontend
    datos_pivot: List[Dict[str, Any]] 
    mensaje: str = "Tabla dinámica generada con éxito"