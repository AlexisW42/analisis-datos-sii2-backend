from datetime import datetime
from pydantic import BaseModel


class PerfiladoResumen(BaseModel):
    registros: int
    variables: int
    completitud: float
    registros_nulos: int
    valores_atipicos: int
    numericas: int
    categoricas: int
    temporales: int


class PerfiladoVariable(BaseModel):
    nombre: str
    tipo: str
    validos: int
    nulos: int
    q1: float | None = None
    q2: float | None = None
    q3: float | None = None
    atipicos: int | None = None


class EstadisticaVariable(BaseModel):
    etiqueta: str
    valor: str


class DistribucionRango(BaseModel):
    rango: str
    porcentaje: float


class DistribucionCantidad(BaseModel):
    rango: str
    cantidad: int


class PerfiladoDetalleVariable(BaseModel):
    nombre: str
    tipo: str
    validos: int
    nulos: int
    estadisticas: list[EstadisticaVariable]
    distribucion: list[DistribucionCantidad]
    porcentajes: list[DistribucionRango]


class PerfiladoResponse(BaseModel):
    dataset_id: int
    dataset_nombre: str
    nombre_archivo: str | None
    fecha_subida: datetime
    resumen: PerfiladoResumen
    variables: list[PerfiladoVariable]
    variable_detalle: PerfiladoDetalleVariable | None = None
