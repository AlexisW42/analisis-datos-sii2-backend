from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from .service import ValidadorArchivo, GestorAlmacenamiento
from app.core.database import get_db
from app.modules.usuarios.service import get_current_user
from app.modules.usuarios.models import Usuario
from app.modules.carga import models

router = APIRouter(prefix="/carga", tags=["carga"])
validador = ValidadorArchivo()
gestor = GestorAlmacenamiento()

@router.get("/")
def get_carga():
    return {"message": "Módulo de Carga (CU01)"}

# ---------------------------------------------------------
# CU01: Cargar DataSet (Endpoint Principal)
# ---------------------------------------------------------
@router.post("/cargar")
def cargar_dataset(
    nombre: str = Form(...),
    descripcion: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Recibe un archivo y sus metadatos, lo valida, lo guarda en disco y registra en la BD.
    """
    try:
        # 1. Validar el archivo
        validador.get_resultado(file)
        
        # 2. Guardar físicamente
        ruta_archivo = gestor.guardar_archivo_fisico(file)
        
        # 3. Guardar en Base de Datos
        nuevo_dataset = models.Dataset(
            nombre=nombre,
            descripcion=descripcion,
            ruta_archivo=ruta_archivo,
            peso_bytes=file.size,
            usuario_id=current_user.id
        )
        db.add(nuevo_dataset)
        db.commit()
        db.refresh(nuevo_dataset)
        
        return {
            "estadoCarga": "Exitoso",
            "message": "Archivo validado y guardado con éxito.",
            "archivoCargado": file.filename,
            "tamañoBytes": file.size,
            "dataset_id": nuevo_dataset.id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
