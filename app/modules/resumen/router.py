import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.carga.models import Dataset
from app.modules.resumen import schemas, service
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.service import get_current_user


router = APIRouter(prefix="/resumen", tags=["resumen ejecutivo"])


def dataset_usuario(dataset_id: int, db: Session, usuario: Usuario) -> Dataset:
    """
    Obtiene un dataset únicamente si pertenece al usuario autenticado.

    Además de recuperar el registro, esta validación evita que un usuario pueda
    consultar o descargar información de datasets pertenecientes a otra cuenta.
    """

    # Se filtra por ambos identificadores en la misma consulta para no revelar si
    # un dataset ajeno existe: en ese caso se responde igual que si no existiera.
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.usuario_id == usuario.id,
    ).first()

    # Centraliza la respuesta 404 para todos los endpoints que usan este helper.
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    return dataset


@router.post("/datasets/{dataset_id}", response_model=schemas.ResumenEjecutivoResponse)
def generar_resumen_ejecutivo(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Genera o recupera el resumen ejecutivo de un dataset del usuario.

    Primero comprueba que el dataset pertenezca al usuario autenticado. Luego
    delega en el servicio la generación del PDF o reutiliza el resumen definitivo
    cuando este ya existe.

    Retorna el identificador del dataset, el estado del resumen y la URL de
    descarga. Los errores esperados se convierten en respuestas HTTP según su
    causa: perfilado pendiente (409), servicio no disponible (503), archivo
    fuente inexistente (404) o error inesperado (500).
    """

    # Valida tanto la existencia del dataset como su pertenencia al usuario.
    dataset = dataset_usuario(dataset_id, db, current_user)
    try:
        # El servicio informa si creó el resumen o reutilizó uno ya disponible.
        ruta, fue_generado = service.obtener_o_generar_resumen(db, dataset)
    except service.PerfiladoRequeridoError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except service.ServicioResumenNoDisponibleError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo físico del dataset no encontrado")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el resumen ejecutivo: {str(exc)}")

    # Mantiene el mismo formato de respuesta en ambos escenarios.
    return schemas.ResumenEjecutivoResponse(
        dataset_id=dataset.id,
        estado="generado" if fue_generado else "disponible",
        resumen_ejecutivo_url=service.url_resumen_ejecutivo(dataset.id),
        message="Resumen ejecutivo generado correctamente" if fue_generado else "El resumen ejecutivo definitivo ya existía",
    )


@router.get("/datasets/{dataset_id}/pdf")
def descargar_resumen_ejecutivo(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Descarga el resumen ejecutivo generado para un dataset del usuario.

    Verifica que el dataset solicitado pertenezca al usuario autenticado y que
    el archivo PDF exista físicamente. Cuando está disponible, lo entrega como
    respuesta descargable con un nombre de archivo seguro y descriptivo.

    Retorna 404 si el dataset no existe, no pertenece al usuario o si su resumen
    ejecutivo todavía no ha sido generado.
    """

    # Impide consultar resúmenes de datasets pertenecientes a otros usuarios.
    dataset = dataset_usuario(dataset_id, db, current_user)

    # Obtiene la ubicación esperada del PDF y comprueba que ya esté generado.
    ruta = service.ruta_resumen_ejecutivo(dataset)
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="El resumen ejecutivo todavía no ha sido generado")

    # Envía el PDF como archivo adjunto usando un nombre apto para descarga.
    return FileResponse(
        ruta,
        media_type="application/pdf",
        filename=f"resumen_ejecutivo_{service.nombre_archivo_seguro(dataset.nombre)}.pdf",
    )
