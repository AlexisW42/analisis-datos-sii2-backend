from fastapi import UploadFile
import pandas as pd
import os
import re
import secrets
import shutil

from app.core.config import settings

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
    def __init__(self):
        self.base_dir = settings.DATASETS_STORAGE_DIR
        os.makedirs(self.base_dir, exist_ok=True)

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
        carpeta_usuario = self.nombre_carpeta_usuario(identificador_usuario)
        ruta_usuario = os.path.join(self.base_dir, carpeta_usuario)
        os.makedirs(ruta_usuario, exist_ok=True)

        ruta_dataset = os.path.join(ruta_usuario, self.nombre_carpeta_dataset(nombre_dataset))
        os.makedirs(ruta_dataset, exist_ok=True)

        extension = f".{file.filename.split('.')[-1].lower()}"
        nombre_archivo = re.sub(r"[^a-zA-Z0-9._-]+", "_", os.path.splitext(file.filename)[0]).strip("._-")
        ruta_completa = os.path.join(ruta_dataset, f"{nombre_archivo or 'dataset'}{extension}")
        
        # Guardar el archivo
        file.file.seek(0)
        with open(ruta_completa, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return ruta_completa

class ControladorCarga:
    pass
