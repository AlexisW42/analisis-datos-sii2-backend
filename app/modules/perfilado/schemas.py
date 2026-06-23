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
    porcentaje_nulos: float
    atipicos: int | None = None
    estado: str


class EstadisticaVariable(BaseModel):
    etiqueta: str
    valor: str


class DistribucionRango(BaseModel):
    rango: str
    porcentaje: float


class PerfiladoDetalleVariable(BaseModel):
    nombre: str
    tipo: str
    validos: int
    nulos: int
    estadisticas: list[EstadisticaVariable]
    distribucion: list[DistribucionRango]
    porcentajes: list[DistribucionRango]


class PerfiladoResponse(BaseModel):
    dataset_id: int
    dataset_nombre: str
    nombre_archivo: str | None
    fecha_subida: datetime
    resumen: PerfiladoResumen
    variables: list[PerfiladoVariable]
    variable_detalle: PerfiladoDetalleVariable | None = None
