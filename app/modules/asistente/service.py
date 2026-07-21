import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESPUESTA_NO_DISPONIBLE = "No puedo responder esa pregunta con el perfilado disponible del dataset."


class GeminiServiceError(Exception):
    pass


def construir_contexto_perfilado(cache_perfilado: dict[str, Any]) -> str:
    """
    Serializa el perfilado completo en JSON compacto para enviarlo al modelo.

    El cache ya contiene resumen del dataset, variables y detalle por columna,
    incluyendo distribuciones y estadisticas como minimo, maximo y valor mas
    frecuente.
    """
    contexto = {
        "dataset_id": cache_perfilado.get("dataset_id"),
        "dataset_nombre": cache_perfilado.get("dataset_nombre"),
        "nombre_archivo": cache_perfilado.get("nombre_archivo"),
        "resumen": cache_perfilado.get("resumen"),
        "variables": cache_perfilado.get("variables"),
        "detalles_variables": cache_perfilado.get("detalles_variables"),
    }
    return json.dumps(contexto, ensure_ascii=False, separators=(",", ":"))


def construir_prompt_usuario(pregunta: str, cache_perfilado: dict[str, Any]) -> str:
    return (
        "Perfilado del dataset en formato JSON:\n"
        f"{construir_contexto_perfilado(cache_perfilado)}\n\n"
        "Pregunta del usuario:\n"
        f"{pregunta.strip()}"
    )


def extraer_texto_respuesta(payload: dict[str, Any]) -> str:
    partes = (
        payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    textos = [parte.get("text", "") for parte in partes if isinstance(parte, dict)]
    return "\n".join(texto.strip() for texto in textos if texto.strip()).strip()


def preguntar_a_gemini(pregunta: str, cache_perfilado: dict[str, Any]) -> str:
    logger.info(
        "Gemini config -> model=%s base_url=%s api_key_set=%s api_key_len=%s",
        settings.GEMINI_MODEL,
        settings.GEMINI_API_BASE_URL,
        bool(settings.GEMINI_API_KEY),
        len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0,
    )

    if not settings.GEMINI_API_KEY:
        raise GeminiServiceError("GEMINI_API_KEY no esta configurada")

    url = f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Eres un analista de datos senior que responde en español de forma clara, "
                        "profesional y útil. Trabaja exclusivamente con el perfilado JSON entregado. "
                        "Puedes interpretar calidad, balance, frecuencias, distribuciones, nulos, "
                        "atípicos, tipos y estadísticas; también puedes orientar sobre posibles "
                        "variables objetivo, variables predictoras, problemas de clasificación o "
                        "regresión, preprocesamiento e ingeniería de características cuando esas "
                        "recomendaciones puedan fundamentarse en los nombres, tipos y métricas de "
                        "las columnas disponibles. Distingue siempre entre un hecho observado en el "
                        "perfilado y una recomendación que debe validarse. No inventes correlaciones, "
                        "causalidad, importancia predictiva, desempeño de modelos ni valores ausentes. "
                        "Si preguntan qué variable usar en clasificación, identifica candidatos "
                        "categóricos plausibles y explica el escenario de uso; no afirmes que son el "
                        "objetivo real sin confirmación. Si la pregunta es ambigua o tiene errores de "
                        "escritura, interpreta la intención más probable y explicita brevemente tu "
                        "supuesto en lugar de rechazarla. Cuando falte una métrica para concluir, "
                        "ofrece la orientación que sí permiten los datos e indica qué análisis "
                        "adicional se necesita. Solo si la pregunta no guarda relación con el dataset "
                        "o no puede ofrecerse ninguna orientación sustentada, responde exactamente: "
                        f"{RESPUESTA_NO_DISPONIBLE}"
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": construir_prompt_usuario(pregunta, cache_perfilado)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 1200,
        },
    }

    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json=payload,
            timeout=30.0,
        )

        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Este log es la clave: te muestra exactamente qué rechazó Gemini
        logger.error(
            "Error HTTP de Gemini (status=%s): %s",
            exc.response.status_code,
            exc.response.text,
        )
        if exc.response.status_code == 429:
            raise GeminiServiceError(
                "El asistente alcanzó temporalmente el límite de consultas. Intenta nuevamente en unos minutos."
            ) from exc
        raise GeminiServiceError(
            "El servicio del asistente no está disponible en este momento. Intenta nuevamente más tarde."
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de conexión al llamar a Gemini: %s", repr(exc))
        raise GeminiServiceError(
            "No fue posible conectar con el servicio del asistente. Intenta nuevamente más tarde."
        ) from exc

    respuesta = extraer_texto_respuesta(response.json())
    return respuesta or RESPUESTA_NO_DISPONIBLE