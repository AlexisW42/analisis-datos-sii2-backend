from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.carga.models import Dataset
from app.modules.perfilado.service import cargar_dataframe_desde_dataset

# Asumiendo que guardaste los archivos anteriores en una carpeta llamada 'pivot' o 'tablas_dinamicas'
# Ajusta esta importación según el nombre exacto de tu carpeta
from . import schemas, service 

router = APIRouter(prefix="/tablas-dinamicas", tags=["Tablas Dinámicas"])

@router.post("/generar", response_model=schemas.PivotResponse)
def generar_tabla_dinamica(
    request: schemas.PivotRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint para generar Tablas Dinámicas (Pivot Tables).
    Cumple con el Proceso Obligatorio 1, 3 y 6 del CU06.
    """
    # 1. Validar que el dataset existe en la base de datos
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dataset con ID {request.dataset_id} no fue encontrado."
        )

    try:
        # 2. Cargar el archivo físico a un DataFrame de Pandas
        # Reutilizamos la función robusta que ya creaste para el módulo de perfilado
        df = cargar_dataframe_desde_dataset(dataset)
        
        # 3. Instanciar nuestro orquestador
        servicio = service.ServicioPivot()
        
        # 4. Empaquetar la configuración solicitada por el usuario
        configuracion = {
            "filas": request.filas,
            "columnas": request.columnas,
            "valores": request.valores,
            "funcion_agregacion": request.funcion_agregacion
        }
        
        # 5. Ejecutar la magia del motor
        datos_pivot = servicio.generar_tablas_dinamicas(df, configuracion)
        
        # 6. Devolver el contrato (Schema) exactamente como lo espera el Frontend
        return schemas.PivotResponse(
            dataset_id=request.dataset_id,
            configuracion=configuracion,
            datos_pivot=datos_pivot
        )

    except ValueError as ve:
        # Captura las excepciones de negocio (Ej. intentar sumar una columna de texto)
        # Retorna un Error 400 (Bad Request) para que el Frontend muestre el mensaje al usuario
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    
    except Exception as e:
        # Captura cualquier otro error interno del servidor o de Pandas
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")