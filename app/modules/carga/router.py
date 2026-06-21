from fastapi import APIRouter, File, UploadFile, HTTPException
from .service import ValidadorArchivo

router = APIRouter(prefix="/carga", tags=["carga"])
validador = ValidadorArchivo()

@router.get("/")
def get_carga():
    return {"message": "Módulo de Carga (CU01)"}

# ---------------------------------------------------------
# CU01: Cargar DataSet (Endpoint Principal)
# ---------------------------------------------------------
@router.post("/cargar")
def cargar_dataset(file: UploadFile = File(...)):
    """
    Recibe un archivo, valida su formato, tamaño y estructura.
    """
    try:
        validador.get_resultado(file)
        
        return {
            "estadoCarga": "Exitoso",
            "message": "Archivo validado con éxito.",
            "archivoCargado": file.filename,
            "tamañoBytes": file.size
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
