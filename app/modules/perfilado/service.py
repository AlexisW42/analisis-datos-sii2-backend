import json
import os
from typing import Any

import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.modules.carga.models import Dataset
from app.modules.carga.service import GestorAlmacenamiento
from app.modules.perfilado import models, schemas

# Se reutiliza el mismo cliente/logica de R2 que usa `carga`, en vez de crear
# una implementacion distinta.
gestor = GestorAlmacenamiento()


def cargar_dataframe_desde_dataset(dataset: Dataset) -> pd.DataFrame:
    """
    Lee el archivo del dataset desde R2 y lo convierte en DataFrame.

    `dataset.ruta_archivo` guarda la key del objeto en R2 (igual que en
    `carga`), no una ruta en disco. Segun la extension, Pandas usa el lector
    correspondiente. Si mas adelante se aceptan otros formatos, este es el
    punto central para agregarlos.
    """
    if not gestor.existe_archivo(dataset.ruta_archivo):
        raise FileNotFoundError("Archivo fisico del dataset no encontrado en R2")

    extension = os.path.splitext(dataset.ruta_archivo)[1].lower()
    buffer = gestor.leer_archivo(dataset.ruta_archivo)

    if extension == ".csv":
        return pd.read_csv(buffer)

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(buffer)

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


def calcular_cuartiles(serie: pd.Series) -> tuple[float | None, float | None, float | None]:
    """
    Calcula Q1, Q2 y Q3 para columnas numericas.

    Los valores no numericos se convierten a `NaN` y se descartan. Si no queda
    ningun valor valido, se retornan `None` para que el frontend muestre que no
    aplica en la tabla general del perfilado.
    """
    valores = pd.to_numeric(serie, errors="coerce").dropna()

    if valores.empty:
        return None, None, None

    return (
        float(valores.quantile(0.25)),
        float(valores.quantile(0.50)),
        float(valores.quantile(0.75)),
    )


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
    valores validos, nulos y atipicos para revision.
    """
    variables: list[schemas.PerfiladoVariable] = []
    total_registros = len(df)

    for columna in df.columns:
        serie = df[columna]
        tipo = clasificar_tipo_variable(serie)
        nulos = int(serie.isna().sum())
        atipicos = contar_atipicos_iqr(serie) if tipo == "Numérica" else None
        q1, q2, q3 = calcular_cuartiles(serie) if tipo == "Numérica" else (None, None, None)

        variables.append(
            schemas.PerfiladoVariable(
                nombre=str(columna),
                tipo=tipo,
                validos=int(total_registros - nulos),
                nulos=nulos,
                q1=q1,
                q2=q2,
                q3=q3,
                atipicos=atipicos,
            )
        )

    return variables


def construir_distribucion_numerica(serie: pd.Series) -> list[schemas.DistribucionCantidad]:
    """
    Agrupa una variable numerica en rangos para graficar barras horizontales.

    `pd.cut` divide los datos en hasta cinco intervalos. Luego se calcula la
    cantidad de valores que cae dentro de cada intervalo.
    """
    valores = pd.to_numeric(serie, errors="coerce").dropna()

    if valores.empty:
        return []

    bins = min(5, max(1, valores.nunique()))
    cortes = pd.cut(valores, bins=bins, duplicates="drop")
    cantidades = cortes.value_counts(sort=False)

    return [
        schemas.DistribucionCantidad(rango=str(indice), cantidad=int(cantidad))
        for indice, cantidad in cantidades.items()
    ]


def construir_cantidades_categoria(serie: pd.Series) -> list[schemas.DistribucionCantidad]:
    """
    Construye la distribucion por cantidad para variables no numericas.

    Se toman los cinco valores mas frecuentes y se devuelve cuantas veces
    aparece cada uno. Esta estructura alimenta el grafico de barras del detalle
    usando cantidades absolutas, no porcentajes.
    """
    valores = serie.dropna()

    if valores.empty:
        return []

    cantidades = valores.astype(str).value_counts().head(5)
    return [
        schemas.DistribucionCantidad(rango=str(indice), cantidad=int(cantidad))
        for indice, cantidad in cantidades.items()
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
        distribucion = construir_cantidades_categoria(serie)

    return schemas.PerfiladoDetalleVariable(
        nombre=variable.nombre,
        tipo=variable.tipo,
        validos=variable.validos,
        nulos=variable.nulos,
        estadisticas=estadisticas,
        distribucion=distribucion,
        porcentajes=construir_porcentajes_categoria(serie),
    )


def construir_cache_perfilado(dataset: Dataset) -> dict[str, Any]:
    """
    Calcula el perfilado completo que se almacena en perfilamiento.json.

    El JSON cacheado guarda los detalles de todas las variables para que el
    frontend pueda cambiar la seleccion sin recalcular el perfilado completo.
    """
    df = cargar_dataframe_desde_dataset(dataset)
    variables = construir_variables(df)
    resumen = construir_resumen(df, variables)
    detalles_variables = {
        variable.nombre: construir_detalle_variable(df, variable).model_dump(mode="json")
        for variable in variables
    }

    return {
        "dataset_id": dataset.id,
        "dataset_nombre": dataset.nombre,
        "nombre_archivo": dataset.nombre_archivo,
        "fecha_subida": dataset.fecha_subida.isoformat(),
        "resumen": resumen.model_dump(mode="json"),
        "variables": [variable.model_dump(mode="json") for variable in variables],
        "detalles_variables": detalles_variables,
    }


def construir_respuesta_desde_cache(cache: dict[str, Any], variable_detalle: str | None = None) -> dict[str, Any]:
    """
    Adapta el JSON cacheado al contrato publico del endpoint.

    El archivo `perfilamiento.json` guarda detalles para todas las variables,
    pero la respuesta HTTP mantiene solo una `variable_detalle`. Si el cliente
    no pide variable o pide una inexistente, se usa la primera disponible.
    """
    variables = cache.get("variables") or []
    detalles_variables = cache.get("detalles_variables") or {}
    variable_objetivo = variable_detalle

    if not variable_objetivo and variables:
        variable_objetivo = variables[0].get("nombre")

    if variable_objetivo not in detalles_variables and variables:
        variable_objetivo = variables[0].get("nombre")

    return {
        "dataset_id": cache["dataset_id"],
        "dataset_nombre": cache["dataset_nombre"],
        "nombre_archivo": cache.get("nombre_archivo"),
        "fecha_subida": cache["fecha_subida"],
        "resumen": cache["resumen"],
        "variables": variables,
        "variable_detalle": detalles_variables.get(variable_objetivo) if variable_objetivo else None,
    }


def key_perfilado_dataset(dataset: Dataset) -> str:
    """
    Devuelve la key en R2 donde se guarda el perfilamiento.json del dataset.

    Se usa el mismo prefijo (carpeta) que el archivo original del dataset, asi
    el perfilado queda junto a el en R2 y se elimina automaticamente cuando
    `carga` borra la carpeta completa del dataset (`eliminar_carpeta`).
    """
    prefijo_dataset = dataset.ruta_archivo.rsplit("/", 1)[0]
    return f"{prefijo_dataset}/perfilamiento.json"


def calcular_peso_mb(tamano_bytes: int) -> float:
    """
    Calcula el peso en megabytes a partir del tamano en bytes del JSON.

    Se redondea a seis decimales para registrar archivos pequenos sin perder
    la referencia de tamano en la tabla `perfilado`.
    """
    return round(tamano_bytes / (1024 * 1024), 6)


def guardar_cache_perfilado(db: Session, dataset: Dataset, cache: dict[str, Any]) -> models.Perfilado:
    """
    Sube el perfilado a R2 y registra su metadata en base de datos.

    Si el dataset ya tiene un registro en `perfilado`, se actualiza la key y
    el peso del JSON. Si es la primera generacion, se crea el registro. R2 es
    la unica fuente de verdad, igual que con el archivo original del dataset.
    """
    key_perfilado = key_perfilado_dataset(dataset)
    contenido = json.dumps(cache, ensure_ascii=False, indent=2).encode("utf-8")

    gestor.subir_bytes(key_perfilado, contenido, content_type="application/json")

    perfilado = db.query(models.Perfilado).filter(models.Perfilado.id_dataset == dataset.id).first()
    if perfilado is None:
        perfilado = models.Perfilado(
            id_dataset=dataset.id,
            path_perfilado=key_perfilado,
            weigth_mb=calcular_peso_mb(len(contenido)),
        )
        db.add(perfilado)
    else:
        perfilado.path_perfilado = key_perfilado
        perfilado.weigth_mb = calcular_peso_mb(len(contenido))

    db.commit()
    db.refresh(perfilado)
    return perfilado


def cargar_cache_perfilado(perfilado: models.Perfilado) -> dict[str, Any] | None:
    """
    Lee el JSON de perfilado previamente generado desde R2.

    Retorna `None` cuando el objeto no existe en R2 o el JSON esta corrupto.
    El llamador usa ese `None` como senal para regenerar el cache.
    """
    if not perfilado.path_perfilado:
        return None

    try:
        buffer = gestor.leer_archivo(perfilado.path_perfilado)
        return json.loads(buffer.read().decode("utf-8"))
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code", "")
        if codigo in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def obtener_o_generar_cache_perfilado(db: Session, dataset: Dataset) -> dict[str, Any]:
    """
    Devuelve el cache completo de perfilado para usos internos.

    Primero intenta usar el registro y archivo existentes. Si no hay metadata,
    falta el JSON o el JSON no es valido, recalcula el perfilado una sola vez y
    lo guarda.
    """
    perfilado = db.query(models.Perfilado).filter(models.Perfilado.id_dataset == dataset.id).first()
    cache = cargar_cache_perfilado(perfilado) if perfilado else None

    if cache is None:
        cache = construir_cache_perfilado(dataset)
        guardar_cache_perfilado(db, dataset, cache)

    return cache


def obtener_o_generar_perfilado(db: Session, dataset: Dataset, variable_detalle: str | None = None) -> dict[str, Any]:
    """
    Punto de entrada del endpoint para obtener un perfilado con cache.

    Reutiliza el cache completo y luego adapta la respuesta al contrato publico
    del frontend, que expone solo un detalle de variable a la vez.
    """
    cache = obtener_o_generar_cache_perfilado(db, dataset)
    return construir_respuesta_desde_cache(cache, variable_detalle)