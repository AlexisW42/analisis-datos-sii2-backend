from fastapi import UploadFile
import pandas as pd
import os
import re
import secrets
from io import BytesIO
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.modules.carga.models import Dataset

class ValidadorArchivo:
    def __init__(self):
        # Atributos de tu Diagrama de Clases
        self.formatos_validos = ['.csv', '.xlsx']
        self.tamano_max_mb = 50  # Límite de 50 Megabytes

    def valida_formato(self, file: UploadFile):
        # Extraemos la extensión del archivo (ej. ".csv")
        extension = f".{file.filename.split('.')[-1].lower()}"
        
        if extension not in self.formatos_validos:
            raise ValueError(f"Formato no válido. Solo se permiten archivos {self.formatos_validos}")
        
        return True

    def validar_tamano(self, file: UploadFile):
        tamano_max_bytes = self.tamano_max_mb * 1024 * 1024
        
        if file.size == 0:
            raise ValueError("El archivo está completamente vacío.")
            
        if file.size > tamano_max_bytes:
            raise ValueError(f"El archivo pesa demasiado. El límite es {self.tamano_max_mb} MB.")
            
        return True

    def validar_estructura(self, file: UploadFile):
        # Leemos solo un pedacito del archivo con Pandas para ver si está corrupto o mal estructurado
        # Esto se hace directo sobre el stream que llega en la request, ANTES de subirlo
        # a R2, así que no depende de dónde guardemos el archivo despues.
        try:
            extension = f".{file.filename.split('.')[-1].lower()}"
            
            if extension == '.csv':
                # Leemos el archivo guardándolo temporalmente en una variable 'df' (DataFrame)
                df = pd.read_csv(file.file, nrows=5)
                
                # Verificamos cuántas columnas reconoció Pandas
                if len(df.columns) < 2:
                    raise ValueError("El archivo CSV no tiene la estructura de una tabla. Verifique que no esté vacío y que use comas (,) como separador.")
                    
            elif extension == '.xlsx':
                df = pd.read_excel(file.file, nrows=5)
                if len(df.columns) < 2:
                    raise ValueError("El archivo Excel no parece contener una tabla de datos válida.")
                
            # Devolvemos el cursor al principio
            file.file.seek(0)
            
        except Exception as e:
            # Si ocurre cualquier error (archivo ilegible, dañado, columnas rotas, asimetría)
            file.file.seek(0)
            raise ValueError(f"El archivo está dañado o su estructura no es válida. Detalle: {str(e)}")
            
        return True

    def get_resultado(self, file: UploadFile) -> bool:
        # Este método orquesta todo. Si una validación falla, lanza el error.
        self.valida_formato(file)
        self.validar_tamano(file)
        self.validar_estructura(file)
        
        return True


class GestorAlmacenamiento:
    """
    Sube, lee y borra los archivos de datasets en Cloudflare R2 usando la API
    S3-compatible (via boto3).

    Nota: `ruta_archivo` en el modelo Dataset ahora guarda la "key" del objeto
    en el bucket de R2 (ej. "usuario_x/mi_dataset_ab12cd34ef/datos.csv"),
    ya no una ruta de archivo en disco.
    """

    def __init__(self):
        self.bucket = settings.R2_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",  # requerido por boto3, R2 lo ignora
            config=Config(
                # boto3 >= 1.36 agrega checksums adicionales por defecto que R2
                # todavia no soporta del todo. Sin esto pueden fallar los
                # upload/delete con errores de firma o de checksum.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def nombre_carpeta_usuario(self, identificador_usuario: str) -> str:
        """
        Convierte el identificador del usuario en un nombre seguro de carpeta.

        Actualmente el usuario no tiene un campo de nombre propio, por eso se
        usa su email. Se reemplazan caracteres especiales para evitar rutas
        invalidas o ambiguas dentro del sistema de archivos.
        """
        nombre_limpio = re.sub(r"[^a-zA-Z0-9._-]+", "_", identificador_usuario.strip().lower())
        return nombre_limpio or "usuario_sin_identificador"

    def nombre_carpeta_dataset(self, nombre_dataset: str) -> str:
        nombre_limpio = re.sub(r"[^a-zA-Z0-9._-]+", "_", nombre_dataset.strip().lower()).strip("._-")
        hash_dataset = secrets.token_hex(5)
        return f"{nombre_limpio or 'dataset'}_{hash_dataset}"

    def guardar_archivo_fisico(self, file: UploadFile, identificador_usuario: str, nombre_dataset: str) -> str:
        """
        Sube el archivo a R2 y devuelve la key del objeto (lo que se guarda
        en Dataset.ruta_archivo).
        """
        carpeta_usuario = self.nombre_carpeta_usuario(identificador_usuario)
        carpeta_dataset = self.nombre_carpeta_dataset(nombre_dataset)

        extension = f".{file.filename.split('.')[-1].lower()}"
        nombre_archivo = re.sub(r"[^a-zA-Z0-9._-]+", "_", os.path.splitext(file.filename)[0]).strip("._-")
        key = f"{carpeta_usuario}/{carpeta_dataset}/{nombre_archivo or 'dataset'}{extension}"

        file.file.seek(0)
        self.client.upload_fileobj(file.file, self.bucket, key)

        return key

    def leer_archivo(self, key: str) -> BytesIO:
        """Descarga un objeto de R2 a memoria y devuelve un buffer legible."""
        buffer = BytesIO()
        self.client.download_fileobj(self.bucket, key, buffer)
        buffer.seek(0)
        return buffer

    def subir_bytes(self, key: str, contenido: bytes, content_type: str = "application/octet-stream") -> None:
        """
        Sube contenido generado en memoria (bytes) a R2, sin pasar por UploadFile.

        A diferencia de `guardar_archivo_fisico` (pensado para el archivo que
        sube el usuario), este metodo sirve para objetos generados por la
        propia aplicacion, como el JSON de perfilado, sin duplicar la
        configuracion del cliente boto3.
        """
        self.client.put_object(Bucket=self.bucket, Key=key, Body=contenido, ContentType=content_type)

    def existe_archivo(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code", "")
            if codigo in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def eliminar_archivo(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def eliminar_carpeta(self, prefix: str) -> None:
        """
        Elimina todos los objetos bajo un prefijo (equivalente a borrar una
        "carpeta" completa, como hacía shutil.rmtree con el disco local).
        Esto borra también archivos generados aparte, como el resumen
        ejecutivo, si viven bajo el mismo prefijo.
        """
        paginator = self.client.get_paginator("list_objects_v2")
        objetos_a_borrar = []
        for pagina in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in pagina.get("Contents", []):
                objetos_a_borrar.append({"Key": obj["Key"]})

        # delete_objects acepta un máximo de 1000 keys por llamada
        for i in range(0, len(objetos_a_borrar), 1000):
            lote = objetos_a_borrar[i:i + 1000]
            if lote:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": lote})


class ControladorCarga:
    pass


# Instancia compartida para las funciones sueltas de este módulo (evita crear
# un cliente boto3 nuevo en cada request de lectura de contenido).
_gestor = GestorAlmacenamiento()


def limpiar_valor_dataset(valor: Any) -> Any:
    """
    Convierte valores de Pandas/Numpy en tipos seguros para JSON.

    La vista de dataset solo necesita representar datos en tabla. Esta funcion
    evita enviar `NaN`, timestamps u otros tipos que FastAPI no serializa bien.
    """
    if pd.isna(valor):
        return None

    if hasattr(valor, "isoformat"):
        return valor.isoformat()

    if hasattr(valor, "item"):
        return valor.item()

    return valor


def cargar_dataframe_dataset(dataset: Dataset) -> pd.DataFrame:
    """
    Lee el archivo desde R2 para visualizar su contenido.

    Se soportan los mismos formatos permitidos por la carga actual: CSV y Excel.
    Si el archivo no existe o tiene un formato no soportado, el endpoint llamador
    transforma la excepcion en una respuesta HTTP adecuada.
    """
    extension = os.path.splitext(dataset.ruta_archivo)[1].lower()
    buffer = _gestor.leer_archivo(dataset.ruta_archivo)

    if extension == ".csv":
        return pd.read_csv(buffer)

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(buffer)

    raise ValueError("Formato de archivo no soportado para visualizacion")


def construir_contenido_dataset(dataset: Dataset, page: int = 1, number_of_records: int = 25) -> dict[str, Any]:
    """
    Construye una respuesta paginada con el contenido visible del dataset.

    El archivo puede ser grande, por eso solo se devuelve la pagina solicitada
    junto con metadata de navegacion. La UI usa esta estructura para renderizar
    una tabla de inspeccion sin cargar todo el dataset en el navegador.
    """
    df = cargar_dataframe_dataset(dataset)
    total_filas = int(df.shape[0])
    total_pages = max(1, (total_filas + number_of_records - 1) // number_of_records)
    current_page = min(max(page, 1), total_pages)
    inicio = (current_page - 1) * number_of_records
    fin = inicio + number_of_records
    muestra = df.iloc[inicio:fin]
    filas = [
        {str(columna): limpiar_valor_dataset(valor) for columna, valor in fila.items()}
        for fila in muestra.to_dict(orient="records")
    ]

    return {
        "id": dataset.id,
        "nombre": dataset.nombre,
        "descripcion": dataset.descripcion,
        "nombre_archivo": dataset.nombre_archivo or os.path.basename(dataset.ruta_archivo),
        "formato": os.path.splitext(dataset.nombre_archivo or dataset.ruta_archivo)[1].replace(".", "").upper(),
        "total_filas": total_filas,
        "total_columnas": int(df.shape[1]),
        "current_page": current_page,
        "number_of_records": number_of_records,
        "total_pages": total_pages,
        "has_previous_page": current_page > 1,
        "has_next_page": current_page < total_pages,
        "columnas": [str(columna) for columna in df.columns],
        "filas": filas,
    }