import os
import re
import shutil
from typing import List
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from .service import ValidadorArchivo, GestorAlmacenamiento
from app.core.database import get_db
from app.modules.usuarios.service import get_current_user
from app.modules.usuarios.models import Usuario
from app.modules.carga import models, schemas

router = APIRouter(prefix="/carga", tags=["carga"])
validador = ValidadorArchivo()
gestor = GestorAlmacenamiento()

@router.get("/")
def get_carga():
    return {"message": "Módulo de Carga (CU01)"}

@router.get("/datasets", response_model=List[schemas.DatasetResponse])
def listar_datasets_usuario(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista los datasets cargados por el usuario autenticado.

    Este endpoint depende de `get_current_user`, por lo que solo responde cuando
    la petición incluye un token Bearer válido. El usuario obtenido desde el
    token se usa para filtrar la consulta y evitar que una persona vea datasets
    pertenecientes a otros usuarios.
    """
    # Se consultan únicamente los datasets cuyo `usuario_id` coincide con el id
    # del usuario autenticado. Este filtro es la regla principal de aislamiento
    # de datos entre usuarios.
    datasets = (
        db.query(models.Dataset)
        .filter(models.Dataset.usuario_id == current_user.id)
        # Los resultados se ordenan del más reciente al más antiguo para que la
        # interfaz pueda mostrar primero las cargas más nuevas.
        .order_by(models.Dataset.fecha_subida.desc())
        .all()
    )

    # Se transforma cada modelo SQLAlchemy en el esquema de respuesta esperado
    # por la API. Esto permite exponer solo los campos necesarios y calcular
    # valores derivados sin devolver directamente la entidad de base de datos.
    return [
        schemas.DatasetResponse(
            id=dataset.id,
            nombre=dataset.nombre,
            descripcion=dataset.descripcion,
            # `nombre_archivo` puede venir vacío en registros antiguos. En ese
            # caso se usa el nombre del archivo tomado desde la ruta física para
            # mantener compatibilidad con datasets ya guardados.
            nombre_archivo=dataset.nombre_archivo or os.path.basename(dataset.ruta_archivo),
            peso_bytes=dataset.peso_bytes,
            fecha_subida=dataset.fecha_subida,
            # El formato se calcula desde la extensión del archivo y se normaliza
            # en mayúsculas para que el cliente reciba valores consistentes como
            # CSV, XLSX o JSON.
            formato=os.path.splitext(dataset.nombre_archivo or dataset.ruta_archivo)[1].replace(".", "").upper(),
            # Por ahora todo dataset listado se considera disponible porque ya
            # fue validado, guardado en disco y registrado en la base de datos.
            estado="Disponible",
        )
        for dataset in datasets
    ]

@router.delete("/datasets/{dataset_id}")
def eliminar_dataset_usuario(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Elimina un dataset perteneciente al usuario autenticado.

    La consulta filtra por `id` y `usuario_id` al mismo tiempo. Asi se evita que
    un usuario pueda borrar datasets de otra cuenta aunque conozca el id.
    """
    dataset = (
        db.query(models.Dataset)
        .filter(
            models.Dataset.id == dataset_id,
            models.Dataset.usuario_id == current_user.id
        )
        .first()
    )

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset no encontrado")

    ruta_archivo = dataset.ruta_archivo
    # Eliminamos la carpeta contenedora del dataset y todos los archivos generados en la plataforma
    if ruta_archivo and os.path.isfile(ruta_archivo):
        try:
            carpeta_dataset = os.path.dirname(ruta_archivo)
            es_carpeta_dataset = re.search(r"_[a-f0-9]{10}$", os.path.basename(carpeta_dataset)) is not None
            if es_carpeta_dataset and os.path.isdir(carpeta_dataset):
                shutil.rmtree(carpeta_dataset)
            else:
                os.remove(ruta_archivo)

        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo eliminar el archivo fisico: {str(exc)}")

    # Una vez eliminado el archivo fisico, se elimina el registro para que deje
    # de aparecer en el panel principal.
    db.delete(dataset)
    db.commit()

    return {"message": "Dataset eliminado correctamente", "dataset_id": dataset_id}

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
        ruta_archivo = gestor.guardar_archivo_fisico(file, current_user.email, nombre)
        
        # 3. Guardar en Base de Datos
        nuevo_dataset = models.Dataset(
            nombre=nombre,
            descripcion=descripcion,
            nombre_archivo=file.filename,
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
