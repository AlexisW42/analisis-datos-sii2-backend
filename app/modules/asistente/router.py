from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.modules.asistente import schemas, service
from app.modules.carga.models import Dataset
from app.modules.perfilado.service import obtener_o_generar_cache_perfilado
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.service import get_current_user


router = APIRouter(prefix="/asistente", tags=["asistente"])


@router.post("/preguntar", response_model=schemas.AsistentePreguntaResponse)
def preguntar_asistente(
    request: schemas.AsistentePreguntaRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Responde una pregunta en lenguaje natural usando Gemini y el perfilado del dataset.

    El dataset se filtra por usuario autenticado para mantener el mismo
    aislamiento usado en carga y perfilado.
    """
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == request.dataset_id,
            Dataset.usuario_id == current_user.id,
        )
        .first()
    )

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    try:
        cache_perfilado = obtener_o_generar_cache_perfilado(db=db, dataset=dataset)
        answer = service.preguntar_a_gemini(request.question, cache_perfilado)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo fisico del dataset no encontrado")
    except service.GeminiServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo responder la pregunta: {str(exc)}")

    return schemas.AsistentePreguntaResponse(
        dataset_id=request.dataset_id,
        question=request.question,
        answer=answer,
        model=settings.GEMINI_MODEL,
    )
