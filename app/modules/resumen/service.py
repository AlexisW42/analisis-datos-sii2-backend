import html
import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import matplotlib
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.core.config import settings
from app.modules.carga.models import Dataset
from app.modules.carga.service import GestorAlmacenamiento
from app.modules.perfilado import models as perfilado_models
from app.modules.perfilado.service import cargar_cache_perfilado, cargar_dataframe_desde_dataset

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
import logging

logger = logging.getLogger(__name__)

MAX_GRAFICAS = 12
UMBRAL_CORRELACION_ALTA = 0.70
ENCABEZADOS_INTERPRETACION = (
    "Contexto del dataset:",
    "Calidad y estructura:",
    "Diagnóstico de balance:",
    "Comportamiento observado:",
    "Implicaciones y riesgos:",
    "Recomendaciones:",
)
AZUL = colors.HexColor("#16324F")
AZUL_MEDIO = colors.HexColor("#315B7D")
AZUL_CLARO = colors.HexColor("#EAF1F6")
GRIS = colors.HexColor("#5E6B75")

# Se reutiliza el mismo cliente/logica de R2 que usa `carga`, en vez de crear
# una implementacion distinta.
gestor = GestorAlmacenamiento()


class PerfiladoRequeridoError(Exception):
    """Indica que no existe un perfilado válido para construir el resumen."""

    pass


class ServicioResumenNoDisponibleError(Exception):
    """Indica que el proveedor externo no pudo generar la interpretación."""

    pass


def key_resumen_ejecutivo_dataset(dataset: Dataset) -> str:
    """Construye la key en R2 del PDF, junto al archivo fuente del dataset.

    Args:
        dataset: Dataset cuyo prefijo de almacenamiento en R2 se utilizará.

    Returns:
        Key del objeto en R2 donde se guarda (o se guardará) el resumen
        ejecutivo, bajo el mismo prefijo que el archivo original del dataset.
    """
    prefijo_dataset = dataset.ruta_archivo.rsplit("/", 1)[0]
    return f"{prefijo_dataset}/resumen_ejecutivo.pdf"


def resumen_ejecutivo_disponible(dataset: Dataset) -> bool:
    """
    Comprueba si el PDF definitivo de un dataset existe en R2.
    """
    return gestor.existe_archivo(key_resumen_ejecutivo_dataset(dataset))


def url_resumen_ejecutivo(dataset_id: int) -> str:
    """
    Devuelve la URL interna del endpoint de descarga para un dataset.
    """
    return f"/resumen/datasets/{dataset_id}/pdf"


def nombre_archivo_seguro(nombre: str) -> str:
    """
    Normaliza un nombre para usarlo de forma segura en una descarga.

    Conserva letras ASCII, números, guiones y guiones bajos; cualquier otro
    grupo de caracteres se reemplaza por un guion bajo. Si el resultado queda
    vacío, se utiliza ``dataset`` como nombre de respaldo.
    """
    limpio = re.sub(r"[^a-zA-Z0-9_-]+", "_", nombre.strip()).strip("_")
    return limpio or "dataset"


def obtener_perfilado_existente(db, dataset: Dataset) -> dict[str, Any]:
    """
    Recupera y valida el perfilado almacenado de un dataset.

    Args:
        db: Sesión de base de datos utilizada para buscar el perfilado.
        dataset: Dataset del que se necesita la información estadística.

    Returns:
        Diccionario deserializado con el perfilado en caché.

    Raises:
        PerfiladoRequeridoError: Si no hay registro de perfilado o su caché no
            puede cargarse como un perfilado válido.
    """
    # Se consulta el registro más reciente disponible para el identificador del
    # dataset y se delega su deserialización al servicio de perfilado, que ya
    # sabe leer el JSON cacheado desde R2.
    perfilado = db.query(perfilado_models.Perfilado).filter(
        perfilado_models.Perfilado.id_dataset == dataset.id
    ).first()
    cache = cargar_cache_perfilado(perfilado) if perfilado else None
    if cache is None:
        raise PerfiladoRequeridoError(
            "El dataset debe tener un perfilado de datos válido antes de generar el resumen ejecutivo"
        )
    return cache


def construir_contexto_balance(df: pd.DataFrame) -> dict[str, Any]:
    """
    Estima una posible variable objetivo y describe el balance de sus clases.

    La elección es heurística: prioriza columnas de 2 a 10 categorías cuyos
    nombres sugieren un resultado, y excluye identificadores evidentes. El
    resultado siempre advierte que la variable debe ser confirmada por un
    analista y no se presenta como el objetivo real del estudio.

    Args:
        df: Datos originales sobre los que se evaluarán las columnas candidatas.

    Returns:
        Contexto con la variable supuesta, distribución, proporciones, razón de
        clases y diagnóstico orientativo. Si no hay una candidata razonable,
        retorna un diagnóstico que explica por qué no puede evaluarse el balance.
    """
    palabras_objetivo = (
        "target", "objetivo", "clase", "class", "label", "resultado", "status", "estado",
        "churn", "abandono", "fraude", "fraud", "default", "incumplimiento", "aprobado",
        "cancel", "salida", "exited", "response", "respuesta", "diagnostico", "diagnóstico",
        "perdida", "pérdida", "loss", "attrition", "retencion", "retención", "retained",
    )
    candidatos: list[tuple[int, int, str]] = []
    for columna in df.columns:
        serie = df[columna].dropna()
        unicos = int(serie.nunique())
        # Las variables constantes o con demasiados valores no son candidatas
        # útiles para este análisis de clasificación orientativo.
        if unicos < 2 or unicos > 10:
            continue
        nombre = str(columna)
        nombre_normalizado = nombre.lower()
        if nombre_normalizado in {"id", "index", "indice", "índice"} or nombre_normalizado.endswith("_id"):
            continue
        coincidencias = sum(1 for palabra in palabras_objetivo if palabra in nombre_normalizado)
        # Se prefieren nombres semánticamente cercanos a un resultado y luego baja cardinalidad.
        candidatos.append((coincidencias, -unicos, nombre))

    if not candidatos:
        return {
            "variable_para_escenario_de_clasificacion": None,
            "diagnostico": "No se identificó una variable objetivo plausible con entre 2 y 10 clases.",
            "advertencia": "No es posible concluir si el dataset está balanceado sin definir el objetivo del estudio.",
        }

    # max() prioriza coincidencias semánticas y, en caso de empate, la menor
    # cardinalidad gracias al valor negativo almacenado en cada candidato.
    _, _, objetivo = max(candidatos)
    conteos = df[objetivo].dropna().astype(str).value_counts()
    total = int(conteos.sum())
    distribucion = [
        {"clase": str(clase), "cantidad": int(cantidad), "porcentaje": round(float(cantidad / total * 100), 2)}
        for clase, cantidad in conteos.items()
    ]
    proporcion_mayor = distribucion[0]["porcentaje"] if distribucion else 0
    proporcion_menor = distribucion[-1]["porcentaje"] if distribucion else 0
    razon = round(proporcion_mayor / proporcion_menor, 2) if proporcion_menor else None
    # Regla descriptiva explícita; no sustituye el criterio propio del caso de negocio.
    nivel = "desbalance marcado" if proporcion_mayor >= 80 or (razon or 0) >= 4 else "desbalance moderado" if proporcion_mayor >= 65 or (razon or 0) >= 2 else "balance relativo"
    return {
        "variable_para_escenario_de_clasificacion": objetivo,
        "numero_clases": len(distribucion),
        "distribucion": distribucion,
        "clase_mayoritaria_porcentaje": proporcion_mayor,
        "clase_minoritaria_porcentaje": proporcion_menor,
        "razon_mayoritaria_vs_minoritaria": razon,
        "diagnostico_orientativo": nivel,
        "criterio_orientativo": "Marcado si la clase mayoritaria alcanza 80% o la razón mayoritaria/minoritaria es al menos 4; moderado desde 65% o razón 2.",
        "advertencia": (
            "El dataset no declara una variable objetivo. Esta variable se usa únicamente para ilustrar "
            "cómo sería el balance si se quisiera clasificar los registros con base en ella."
        ),
    }


def interpretar_perfilado_con_gemini(cache: dict[str, Any], variables_seleccionadas: list[str], df: pd.DataFrame) -> str:
    """Solicita a Gemini una interpretación ejecutiva basada en el perfilado.

    Args:
        cache: Perfilado estadístico previamente calculado para el dataset.
        variables_seleccionadas: Columnas escogidas para las gráficas del PDF.
        df: DataFrame usado para calcular el contexto orientativo de balance.

    Returns:
        Texto plano en español, estructurado con los encabezados exigidos en el
        prompt y listo para incorporarse al informe.

    Raises:
        ServicioResumenNoDisponibleError: Si falta la clave de API, ocurre un
            error HTTP o la respuesta no contiene texto interpretable.
    """
    if not settings.GEMINI_API_KEY:
        raise ServicioResumenNoDisponibleError(
            "El servicio de generación de resumen no está disponible en este momento. Intente más tarde"
        )

    # Solo se envía la información necesaria para fundamentar la interpretación;
    # el balance se calcula localmente para limitar conclusiones inventadas.
    contexto = {
        "dataset_nombre": cache.get("dataset_nombre"),
        "resumen": cache.get("resumen"),
        "variables": cache.get("variables"),
        "detalles_variables": cache.get("detalles_variables"),
        "variables_seleccionadas_para_graficas": variables_seleccionadas,
        "analisis_balance_orientativo": construir_contexto_balance(df),
    }
    prompt = (
        "Redacta en español un resumen ejecutivo profesional, preciso y orientado a la toma de decisiones, como lo "
        "haría un analista de datos senior. Basa cada afirmación exclusivamente en el perfilado JSON suministrado. "
        "Describe qué información contiene el dataset y qué análisis permiten sus variables, sin inventar quién lo "
        "subió, qué empresa lo utiliza, su procedencia, su finalidad real, una necesidad de negocio ni resultados que "
        "no estén presentes en los datos. No uses expresiones especulativas como 'podría ser utilizado por una empresa'. "
        "No afirmes que existe una variable objetivo porque el dataset no la declara. En el diagnóstico de balance, "
        "presenta la variable calculada únicamente como un escenario condicional con una redacción de este tipo: "
        "'Si se desea clasificar los registros con base en «X», debe considerarse que...'. Expón después su distribución, "
        "la diferencia entre las clases y las implicaciones técnicas del balance observado. No digas 'se ha supuesto que "
        "la variable objetivo es X'. Si no hay una variable apropiada, explica que el balance de clases solo puede "
        "evaluarse después de definir un objetivo de clasificación. No apliques el concepto de balance de clases a una "
        "variable continua. Describe completitud, nulos y atípicos con tono neutral; evita calificativos vagos como "
        "'excelente' si no aportan una decisión. Prioriza hallazgos, riesgos y acciones concretas, evita repeticiones y "
        "distingue siempre observaciones de recomendaciones. Aclara que asociación no implica causalidad. Entrega texto "
        "plano usando exactamente estos encabezados, cada uno seguido por un párrafo sustancial: Contexto del dataset:, "
        "Calidad y estructura:, Diagnóstico de balance:, Comportamiento observado:, Implicaciones y riesgos:, "
        "Recomendaciones:. No uses Markdown ni listas.\n\n"
        + json.dumps(contexto, ensure_ascii=False, separators=(",", ":"))
    )
    # Una temperatura baja favorece una redacción estable y apegada a los datos.
    # Gemini 2.5 Flash usa razonamiento dinámico por defecto; se desactiva aquí
    # para reservar el presupuesto de salida a la interpretación visible.
    payload = {
        "systemInstruction": {"parts": [{"text": "Eres un analista senior que prepara informes ejecutivos basados exclusivamente en evidencia estadística suministrada."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 8192,
        },
    }
    try:
        response = httpx.post(
            f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload, timeout=45.0,
        )
        response.raise_for_status()
        candidato = response.json().get("candidates", [{}])[0]
        partes = candidato.get("content", {}).get("parts", [])
        texto = "\n".join(p.get("text", "").strip() for p in partes if p.get("text", "").strip())
        encabezados_faltantes = [
            encabezado for encabezado in ENCABEZADOS_INTERPRETACION
            if encabezado not in texto
        ]
        if candidato.get("finishReason") == "MAX_TOKENS" or encabezados_faltantes:
            logger.error(
                "Interpretacion incompleta -> finishReason=%s encabezados_faltantes=%s texto_len=%s",
                candidato.get("finishReason"), encabezados_faltantes, len(texto),
            )
            raise ValueError("Gemini devolvió una interpretación incompleta")
        return texto
    except httpx.HTTPStatusError as exc:
        logger.error("Error HTTP de Gemini en resumen (status=%s): %s", exc.response.status_code, exc.response.text)
        raise ServicioResumenNoDisponibleError(
            "El servicio de generación de resumen no está disponible en este momento. Intente más tarde"
        ) from exc
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        logger.exception("Error inesperado generando interpretacion con Gemini")
        raise ServicioResumenNoDisponibleError(
            "El servicio de generación de resumen no está disponible en este momento. Intente más tarde"
        ) from exc

def seleccionar_variables_diversas(df: pd.DataFrame, cache: dict[str, Any]) -> list[str]:
    """Selecciona hasta ``MAX_GRAFICAS`` variables informativas y diversas.

    Las variables se ordenan priorizando aquellas con más nulos o atípicos, pues
    suelen aportar señales relevantes de calidad. Entre las numéricas se evita
    incluir pares cuya correlación de Pearson supere el umbral configurado. Las
    categóricas y temporales se agregan después porque requieren una lectura que
    la correlación numérica no representa.

    Args:
        df: DataFrame que contiene los valores de las columnas candidatas.
        cache: Perfilado con nombres, tipos y métricas de calidad por variable.

    Returns:
        Lista ordenada de nombres de columnas existentes en el DataFrame.
    """
    variables = cache.get("variables") or []
    ordenadas = sorted(
        variables,
        key=lambda v: ((v.get("nulos") or 0) + (v.get("atipicos") or 0), v.get("validos") or 0),
        reverse=True,
    )
    numericas = [v["nombre"] for v in ordenadas if v.get("tipo") == "Numérica" and v["nombre"] in df]
    no_numericas = [v["nombre"] for v in ordenadas if v.get("tipo") != "Numérica" and v["nombre"] in df]
    seleccion: list[str] = []

    if numericas:
        correlaciones = df[numericas].apply(pd.to_numeric, errors="coerce").corr().abs()
        for nombre in numericas:
            if all(
                pd.isna(correlaciones.loc[nombre, previa])
                or correlaciones.loc[nombre, previa] <= UMBRAL_CORRELACION_ALTA
                for previa in seleccion if previa in numericas
            ):
                seleccion.append(nombre)
            if len(seleccion) >= MAX_GRAFICAS:
                break

    # Las categóricas/temporales añaden dimensiones que Pearson no representa.
    for nombre in no_numericas:
        if len(seleccion) >= MAX_GRAFICAS:
            break
        seleccion.append(nombre)
    return seleccion


def crear_grafica_frecuencia(serie: pd.Series, nombre: str, tipo: str) -> io.BytesIO:
    """Crea una gráfica de frecuencia en memoria para incluirla en el PDF.

    Para variables numéricas genera un histograma de hasta diez intervalos. Para
    los demás tipos muestra horizontalmente las ocho categorías más frecuentes.

    Args:
        serie: Valores de la variable que se representará.
        nombre: Nombre visible de la variable.
        tipo: Tipo informado por el perfilado; ``Numérica`` activa el histograma.

    Returns:
        Búfer PNG posicionado al inicio y listo para ser leído por ReportLab.
    """
    fig, ax = plt.subplots(figsize=(4.0, 2.35), dpi=150)
    valores = serie.dropna()
    if tipo == "Numérica":
        numericos = pd.to_numeric(valores, errors="coerce").dropna()
        ax.hist(numericos, bins=min(10, max(1, int(numericos.nunique()))), color="#315B7D", edgecolor="white")
        ax.set_ylabel("Frecuencia")
    else:
        conteos = valores.astype(str).value_counts().head(8).sort_values()
        etiquetas = [x if len(x) <= 18 else x[:15] + "…" for x in conteos.index]
        ax.barh(etiquetas, conteos.values, color="#4E8098")
        ax.set_xlabel("Frecuencia")
    ax.set_title(nombre if len(nombre) <= 34 else nombre[:31] + "…", fontsize=9, fontweight="bold", loc="left")
    ax.tick_params(axis="both", labelsize=7)
    ax.grid(axis="y" if tipo == "Numérica" else "x", alpha=0.18)
    for borde in ("top", "right"):
        ax.spines[borde].set_visible(False)
    fig.tight_layout()
    # El búfer evita crear archivos temporales independientes por cada gráfica.
    salida = io.BytesIO()
    fig.savefig(salida, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    salida.seek(0)
    return salida


def _pie_pagina(canvas, doc):
    canvas.saveState()
    ancho, _ = A4
    canvas.setStrokeColor(colors.HexColor("#D8E0E6"))
    canvas.line(1.5 * cm, 1.25 * cm, ancho - 1.5 * cm, 1.25 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(1.5 * cm, 0.8 * cm, "Resumen Ejecutivo · Análisis de Datos SII2")
    canvas.drawRightString(ancho - 1.5 * cm, 0.8 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph(html.escape(str(texto)).replace("\n", "<br/>"), estilo)


def _interpretacion_con_subtitulos(texto: str, estilo) -> Paragraph:
    """
    Convierte la interpretación en un párrafo con subtítulos en negrita.

    El contenido completo se escapa antes de añadir las únicas etiquetas HTML
    controladas por la aplicación, evitando interpretar marcado generado por el
    proveedor externo.
    """
    texto_seguro = html.escape(texto)
    for encabezado in ENCABEZADOS_INTERPRETACION:
        texto_seguro = texto_seguro.replace(encabezado, f"<b>{encabezado}</b>")
    return Paragraph(texto_seguro.replace("\n", "<br/>"), estilo)


def generar_pdf(dataset: Dataset, cache: dict[str, Any], df: pd.DataFrame, interpretacion: str, variables: list[str], destino: io.BytesIO) -> None:
    """
    Renderiza el resumen ejecutivo completo con ReportLab.

    `destino` es un buffer en memoria (BytesIO); ReportLab acepta un objeto
    tipo archivo igual que aceptaria una ruta en disco, asi que el PDF nunca
    toca el disco local y queda listo para subirse directo a R2.
    """
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("Titulo", parent=estilos["Title"], textColor=AZUL, fontSize=25, leading=29, alignment=TA_LEFT)
    h1 = ParagraphStyle("H1", parent=estilos["Heading1"], textColor=AZUL, fontSize=15, leading=19, spaceBefore=10, spaceAfter=8)
    cuerpo = ParagraphStyle(
        "Cuerpo",
        parent=estilos["BodyText"],
        textColor=colors.HexColor("#273642"),
        fontSize=9.5,
        leading=14,
        alignment=TA_JUSTIFY,
    )
    pequeno = ParagraphStyle("Pequeno", parent=cuerpo, fontSize=8, leading=11, textColor=GRIS)
    metrica = ParagraphStyle("Metrica", parent=cuerpo, fontSize=16, leading=19, alignment=TA_CENTER, textColor=AZUL)
    etiqueta = ParagraphStyle("Etiqueta", parent=pequeno, alignment=TA_CENTER)
    doc = SimpleDocTemplate(destino, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.7*cm)
    story = [_p("RESUMEN EJECUTIVO", titulo), Spacer(1, .25*cm), _p(dataset.nombre, ParagraphStyle("Sub", parent=h1, fontSize=18))]
    story += [_p(dataset.descripcion or "Dataset sin descripción registrada.", cuerpo), Spacer(1, .35*cm)]
    metadatos = [
        ["Archivo original", dataset.nombre_archivo or os.path.basename(dataset.ruta_archivo)],
        ["Fecha de generación", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
    ]
    tabla_meta = Table(metadatos, colWidths=[4.2*cm, 12.1*cm])
    tabla_meta.setStyle(TableStyle([("BACKGROUND", (0,0),(0,-1), AZUL_CLARO), ("TEXTCOLOR",(0,0),(0,-1),AZUL), ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTNAME",(1,0),(1,-1),"Helvetica"), ("FONTSIZE",(0,0),(-1,-1),8.5), ("GRID",(0,0),(-1,-1),.3,colors.HexColor("#CBD6DE")), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("PADDING",(0,0),(-1,-1),6)]))
    story += [tabla_meta, Spacer(1, .35*cm), _p("Indicadores principales", h1)]
    r = cache.get("resumen") or {}
    metricas = [(r.get("registros",0),"Registros"),(r.get("variables",0),"Variables"),(f"{r.get('completitud',0)}%","Completitud"),(r.get("registros_nulos",0),"Registros nulos"),(r.get("valores_atipicos",0),"Atípicos")]
    cards = [[_p(v, metrica) for v,_ in metricas], [_p(e, etiqueta) for _,e in metricas]]
    tabla_cards = Table(cards, colWidths=[3.25*cm]*5)
    tabla_cards.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),AZUL_CLARO),("BOX",(0,0),(-1,-1),.6,colors.HexColor("#CBD6DE")),("INNERGRID",(0,0),(-1,-1),.6,colors.white),("TOPPADDING",(0,0),(-1,0),10),("BOTTOMPADDING",(0,1),(-1,1),9)]))
    story += [
        tabla_cards,
        Spacer(1, .4 * cm),
        _p("Interpretación ejecutiva", h1),
        _interpretacion_con_subtitulos(interpretacion, cuerpo),
    ]
    story += [PageBreak(), _p("Frecuencias seleccionadas", h1), _p(
        "No se muestran todas las frecuencias para evitar repetición visual y conclusiones redundantes. Variables numéricas con correlación lineal alta pueden describir una dimensión similar del dataset; por ello se conservan preferentemente variables con correlaciones bajas o moderadas entre sí. Esta selección mejora la cobertura de dimensiones diferentes, aunque correlación no equivale a causalidad y las variables categóricas requieren criterios distintos.", cuerpo), Spacer(1,.25*cm)]
    tipos = {v["nombre"]: v.get("tipo", "Categórica") for v in cache.get("variables", [])}
    graficas = [Image(crear_grafica_frecuencia(df[n], n, tipos.get(n,"Categórica")), width=8.0*cm, height=4.7*cm) for n in variables]
    filas = [graficas[i:i+2] + ([""] if len(graficas[i:i+2]) == 1 else []) for i in range(0,len(graficas),2)]
    if filas:
        tabla_graficas = Table(filas, colWidths=[8.25*cm,8.25*cm])
        tabla_graficas.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        story.append(tabla_graficas)
    story += [PageBreak(), _p("Anexo de variables", h1)]
    encabezado = [_p(x, ParagraphStyle("TH", parent=pequeno, textColor=colors.white, fontName="Helvetica-Bold")) for x in ["Variable","Tipo","Válidos","Nulos","Atípicos"]]
    datos = [encabezado]
    for v in cache.get("variables", []):
        datos.append([_p(v.get("nombre",""), pequeno), _p(v.get("tipo",""), pequeno), str(v.get("validos",0)), str(v.get("nulos",0)), str(v.get("atipicos") if v.get("atipicos") is not None else "N/A")])
    tabla = Table(datos, repeatRows=1, colWidths=[6.4*cm,3.1*cm,2.3*cm,2.3*cm,2.3*cm])
    tabla.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),AZUL),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#CBD6DE")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,AZUL_CLARO]),("FONTSIZE",(0,1),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(2,1),(-1,-1),"RIGHT"),("PADDING",(0,0),(-1,-1),5)]))
    story.append(tabla)
    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)


def obtener_o_generar_resumen(db, dataset: Dataset) -> tuple[str, bool]:
    """
    Devuelve la key en R2 del resumen ejecutivo, generandolo si aun no existe.

    Si el PDF definitivo ya existe en R2 se reutiliza tal cual. En caso
    contrario se arma por completo en memoria (perfilado + dataframe leidos
    desde R2 + interpretacion de Gemini) y se sube una unica vez al bucket,
    evitando dejar objetos parciales si algo falla a mitad de camino.
    """
    key_destino = key_resumen_ejecutivo_dataset(dataset)
    if gestor.existe_archivo(key_destino):
        return key_destino, False

    cache = obtener_perfilado_existente(db, dataset)
    # `cargar_dataframe_desde_dataset` ya valida contra R2 y lanza
    # FileNotFoundError si el archivo fuente no existe; no hace falta
    # duplicar ese chequeo aqui.
    df = cargar_dataframe_desde_dataset(dataset)
    variables = seleccionar_variables_diversas(df, cache)
    interpretacion = interpretar_perfilado_con_gemini(cache, variables, df)

    buffer = io.BytesIO()
    generar_pdf(dataset, cache, df, interpretacion, variables, buffer)
    buffer.seek(0)
    gestor.subir_bytes(key_destino, buffer.read(), content_type="application/pdf")

    return key_destino, True