import os
from typing import Any

import pandas as pd

from app.modules.carga.models import Dataset
from app.modules.perfilado import schemas


def cargar_dataframe_desde_dataset(dataset: Dataset) -> pd.DataFrame:
    """
    Lee el archivo fisico asociado a un dataset y lo convierte en DataFrame.

    El dataset guarda la ruta donde quedo almacenado el archivo. Segun la
    extension, Pandas usa el lector correspondiente. Si mas adelante se aceptan
    otros formatos, este es el punto central para agregarlos.
    """
    extension = os.path.splitext(dataset.ruta_archivo)[1].lower()

    if extension == ".csv":
        return pd.read_csv(dataset.ruta_archivo)

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(dataset.ruta_archivo)

    raise ValueError("Formato de archivo no soportado para perfilado")


def clasificar_tipo_variable(serie: pd.Series) -> str:
    """
    Clasifica una columna en numerica, temporal o categorica.

    Primero se revisan tipos nativos de Pandas. Si la columna no es numerica ni
    fecha, se intenta una conversion suave a fecha para detectar columnas
    temporales guardadas como texto.
    """
    if pd.api.types.is_numeric_dtype(serie):
        return "Numérica"

    if pd.api.types.is_datetime64_any_dtype(serie):
        return "Temporal"

    valores_no_nulos = serie.dropna()
    if not valores_no_nulos.empty:
        fechas = pd.to_datetime(valores_no_nulos, errors="coerce")
        if fechas.notna().mean() >= 0.8:
            return "Temporal"

    return "Categórica"


def contar_atipicos_iqr(serie: pd.Series) -> int:
    """
    Cuenta valores atipicos de una columna numerica usando la regla IQR.

    IQR significa rango intercuartil. Se calcula Q1 y Q3, luego se consideran
    atipicos los valores menores a Q1 - 1.5*IQR o mayores a Q3 + 1.5*IQR.
    """
    valores = pd.to_numeric(serie, errors="coerce").dropna()

    if valores.empty:
        return 0

    q1 = valores.quantile(0.25)
    q3 = valores.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return 0

    limite_inferior = q1 - (1.5 * iqr)
    limite_superior = q3 + (1.5 * iqr)
    return int(((valores < limite_inferior) | (valores > limite_superior)).sum())


def formatear_numero(valor: Any) -> str:
    """
    Convierte numeros de Pandas/Python en texto legible para la interfaz.

    La respuesta JSON podria enviar numeros crudos, pero este modulo prepara
    etiquetas de estadisticas ya listas para mostrar en tarjetas pequenas.
    """
    if pd.isna(valor):
        return "N/D"

    if isinstance(valor, float):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return str(valor)


def construir_resumen(df: pd.DataFrame, variables: list[schemas.PerfiladoVariable]) -> schemas.PerfiladoResumen:
    """
    Construye las metricas generales del dataset a partir del DataFrame.

    Estas metricas alimentan las tarjetas superiores del mockup: registros,
    variables, completitud, celdas nulas y valores atipicos detectados.
    """
    total_celdas = int(df.shape[0] * df.shape[1])
    total_nulos = int(df.isna().sum().sum())
    completitud = 100.0 if total_celdas == 0 else round(((total_celdas - total_nulos) / total_celdas) * 100, 1)

    return schemas.PerfiladoResumen(
        registros=int(df.shape[0]),
        variables=int(df.shape[1]),
        completitud=completitud,
        registros_nulos=total_nulos,
        valores_atipicos=sum(variable.atipicos or 0 for variable in variables),
        numericas=sum(1 for variable in variables if variable.tipo == "Numérica"),
        categoricas=sum(1 for variable in variables if variable.tipo == "Categórica"),
        temporales=sum(1 for variable in variables if variable.tipo == "Temporal"),
    )


def construir_variables(df: pd.DataFrame) -> list[schemas.PerfiladoVariable]:
    """
    Genera el diagnostico fila por fila para la tabla de variables.

    Cada columna del dataset se convierte en un resumen con tipo, cantidad de
    valores validos, nulos, atipicos y estado visual para revision.
    """
    variables: list[schemas.PerfiladoVariable] = []
    total_registros = len(df)

    for columna in df.columns:
        serie = df[columna]
        tipo = clasificar_tipo_variable(serie)
        nulos = int(serie.isna().sum())
        porcentaje_nulos = 0.0 if total_registros == 0 else round((nulos / total_registros) * 100, 2)
        atipicos = contar_atipicos_iqr(serie) if tipo == "Numérica" else None
        estado = "Revisar" if nulos > 0 or (atipicos or 0) > 0 else "Correcta"

        variables.append(
            schemas.PerfiladoVariable(
                nombre=str(columna),
                tipo=tipo,
                validos=int(total_registros - nulos),
                nulos=nulos,
                porcentaje_nulos=porcentaje_nulos,
                atipicos=atipicos,
                estado=estado,
            )
        )

    return variables


def construir_distribucion_numerica(serie: pd.Series) -> list[schemas.DistribucionRango]:
    """
    Agrupa una variable numerica en rangos para graficar barras horizontales.

    `pd.cut` divide los datos en hasta cinco intervalos. Luego se calcula que
    porcentaje de valores cae dentro de cada intervalo.
    """
    valores = pd.to_numeric(serie, errors="coerce").dropna()

    if valores.empty:
        return []

    bins = min(5, max(1, valores.nunique()))
    cortes = pd.cut(valores, bins=bins, duplicates="drop")
    porcentajes = cortes.value_counts(normalize=True, sort=False) * 100

    return [
        schemas.DistribucionRango(rango=str(indice), porcentaje=round(float(porcentaje), 1))
        for indice, porcentaje in porcentajes.items()
    ]


def construir_porcentajes_categoria(serie: pd.Series) -> list[schemas.DistribucionRango]:
    """
    Calcula los porcentajes de los valores mas frecuentes de una variable.

    Para variables categoricas muestra categorias; para numericas puede servir
    como tabla complementaria si hay pocos valores repetidos.
    """
    valores = serie.dropna()

    if valores.empty:
        return []

    porcentajes = valores.astype(str).value_counts(normalize=True).head(5) * 100
    return [
        schemas.DistribucionRango(rango=str(indice), porcentaje=round(float(porcentaje), 1))
        for indice, porcentaje in porcentajes.items()
    ]


def construir_detalle_variable(df: pd.DataFrame, variable: schemas.PerfiladoVariable) -> schemas.PerfiladoDetalleVariable:
    """
    Construye el panel lateral de detalle para una variable especifica.

    Si la variable es numerica, se calculan minimo, maximo, promedio, mediana,
    desviacion estandar y cuartiles. Para otras variables, se muestran datos de
    frecuencia porque no aplican estadisticas numericas.
    """
    serie = df[variable.nombre]
    estadisticas: list[schemas.EstadisticaVariable] = []

    if variable.tipo == "Numérica":
        valores = pd.to_numeric(serie, errors="coerce").dropna()
        q1 = valores.quantile(0.25) if not valores.empty else None
        q3 = valores.quantile(0.75) if not valores.empty else None

        estadisticas = [
            schemas.EstadisticaVariable(etiqueta="Mínimo", valor=formatear_numero(valores.min() if not valores.empty else None)),
            schemas.EstadisticaVariable(etiqueta="Máximo", valor=formatear_numero(valores.max() if not valores.empty else None)),
            schemas.EstadisticaVariable(etiqueta="Promedio", valor=formatear_numero(valores.mean() if not valores.empty else None)),
            schemas.EstadisticaVariable(etiqueta="Mediana", valor=formatear_numero(valores.median() if not valores.empty else None)),
            schemas.EstadisticaVariable(etiqueta="Desv. estándar", valor=formatear_numero(valores.std() if len(valores) > 1 else 0)),
            schemas.EstadisticaVariable(etiqueta="Cuartiles", valor=f"Q1 {formatear_numero(q1)} · Q3 {formatear_numero(q3)}"),
        ]
        distribucion = construir_distribucion_numerica(serie)
    else:
        estadisticas = [
            schemas.EstadisticaVariable(etiqueta="Valores únicos", valor=str(int(serie.nunique(dropna=True)))),
            schemas.EstadisticaVariable(etiqueta="Más frecuente", valor=str(serie.mode(dropna=True).iloc[0]) if not serie.mode(dropna=True).empty else "N/D"),
            schemas.EstadisticaVariable(etiqueta="Nulos", valor=str(variable.nulos)),
        ]
        distribucion = construir_porcentajes_categoria(serie)

    return schemas.PerfiladoDetalleVariable(
        nombre=variable.nombre,
        tipo=variable.tipo,
        validos=variable.validos,
        nulos=variable.nulos,
        estadisticas=estadisticas,
        distribucion=distribucion,
        porcentajes=construir_porcentajes_categoria(serie),
    )


def generar_perfilado(dataset: Dataset, variable_detalle: str | None = None) -> schemas.PerfiladoResponse:
    """
    Orquesta el perfilado completo de un dataset.

    Esta es la funcion principal del modulo: lee el archivo, calcula variables,
    resumen general y selecciona una variable para el panel de detalle.
    """
    df = cargar_dataframe_desde_dataset(dataset)
    variables = construir_variables(df)
    resumen = construir_resumen(df, variables)

    variable_objetivo = None
    if variables:
        variable_objetivo = next((variable for variable in variables if variable.nombre == variable_detalle), variables[0])

    return schemas.PerfiladoResponse(
        dataset_id=dataset.id,
        dataset_nombre=dataset.nombre,
        nombre_archivo=dataset.nombre_archivo,
        fecha_subida=dataset.fecha_subida,
        resumen=resumen,
        variables=variables,
        variable_detalle=construir_detalle_variable(df, variable_objetivo) if variable_objetivo else None,
    )
