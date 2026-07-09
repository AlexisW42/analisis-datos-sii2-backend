import json
from typing import Any

import httpx

from app.core.config import settings


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
    if not settings.GEMINI_API_KEY:
        raise GeminiServiceError("GEMINI_API_KEY no esta configurada")

    url = f"{settings.GEMINI_API_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Eres un asistente de analisis de datos. Responde solo con base en el "
                        "perfilado JSON entregado. Puedes responder preguntas sobre balance del "
                        "dataset, frecuencias, categorias mas repetidas, nulos, tipos de variables "
                        "y estadisticas numericas disponibles. Si la pregunta esta fuera del "
                        "contexto del dataset o el perfilado no contiene la informacion suficiente, "
                        f"responde exactamente: {RESPUESTA_NO_DISPONIBLE}"
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
            "maxOutputTokens": 512,
        },
    }

    try:
        response = httpx.post(
            url,
            params={"key": settings.GEMINI_API_KEY},
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeminiServiceError(f"No se pudo consultar Gemini: {str(exc)}") from exc

    respuesta = extraer_texto_respuesta(response.json())
    return respuesta or RESPUESTA_NO_DISPONIBLE
