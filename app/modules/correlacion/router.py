from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.carga.models import Dataset
from app.modules.perfilado.service import cargar_dataframe_desde_dataset
from app.modules.correlacion import schemas, service

router = APIRouter(prefix="/correlacion", tags=["Matriz de Correlación"])

@router.post("/generar", response_model=schemas.CorrelacionResponse)
def generar_analisis_correlacion(
    request: schemas.CorrelacionRequest,
    db: Session = Depends(get_db)
):
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dataset con ID {request.dataset_id} no fue encontrado."
        )

    try:
        df = cargar_dataframe_desde_dataset(dataset)
        servicio = service.ServicioCorrelacion()
        resultado = servicio.generar_matriz_correlacion(
            df=df,
            estrategia_nulos=request.estrategia_nulos,
            metodo=request.metodo
        )
        return resultado

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))