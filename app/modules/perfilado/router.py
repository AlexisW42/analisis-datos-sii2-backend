from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.carga.models import Dataset
from app.modules.perfilado import schemas, service
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.service import get_current_user


router = APIRouter(prefix="/perfilado", tags=["perfilado"])


@router.get("/datasets/{dataset_id}", response_model=schemas.PerfiladoResponse)
def obtener_perfilado_dataset(
    dataset_id: int,
    variable: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Devuelve el perfilado estadistico de un dataset del usuario autenticado.

    El filtro por `usuario_id` es obligatorio para que una persona solo pueda
    perfilar datasets propios. El parametro opcional `variable` permite pedir
    el detalle lateral de una columna especifica.
    """
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.usuario_id == current_user.id,
        )
        .first()
    )

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    try:
        return service.generar_perfilado(dataset=dataset, variable_detalle=variable)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo fisico del dataset no encontrado")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el perfilado: {str(exc)}")
