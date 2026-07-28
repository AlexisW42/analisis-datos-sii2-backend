from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class PivotRequest(BaseModel):
    dataset_id: int
    filas: List[str] = Field(..., description="Lista de variables para agrupar en las filas")
    columnas: List[str] = Field(default=[], description="Lista de variables para agrupar en las columnas")
    valores: str = Field(..., description="La variable numérica o categórica a medir")
    funcion_agregacion: str = Field(
        ..., 
        # Agregamos 'median' a la lista de documentación
        description="Operación matemática: 'sum', 'mean', 'count', 'max', 'min', 'median'" 
    )

class PivotResponse(BaseModel):
    dataset_id: int
    configuracion: dict
    datos_pivot: List[Dict[str, Any]] 
    mensaje: str = "Tabla dinámica generada con éxito"