from pydantic import BaseModel, Field
from typing import List, Dict, Any

# ==========================================
# ESQUEMAS DE ENTRADA (Request)
# ==========================================
class CorrelacionRequest(BaseModel):
    dataset_id: int = Field(..., description="ID del dataset validado en la base de datos")
    estrategia_nulos: str = Field(
        default="ignorar", 
        description="Opciones válidas: ignorar, eliminar_filas, imputar_promedio"
    )
    metodo: str = Field(
        default="pearson", 
        description="Algoritmo matemático: pearson, spearman, kendall"
    )

# ==========================================
# ESQUEMAS DE SALIDA (Response)
# ==========================================
class CeldaMatriz(BaseModel):
    id_x: str
    id_y: str
    valor: float

class RelacionFuerte(BaseModel):
    variable_1: str
    variable_2: str
    coeficiente: float
    tipo: str

class CorrelacionResponse(BaseModel):
    configuracion: Dict[str, str]
    aviso_omision: str
    matriz_calor: List[CeldaMatriz]
    relaciones_fuertes: List[RelacionFuerte]
    variables_claves: List[str]
    matriz_significancia: Dict[str, Dict[str, float]]