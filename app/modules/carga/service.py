from fastapi import UploadFile
import pandas as pd

class ValidadorArchivo:
    def __init__(self):
        # Atributos de tu Diagrama de Clases
        self.formatos_validos = ['.csv', '.xlsx']
        self.tamano_max_mb = 50  # Límite de 50 Megabytes

    def valida_formato(self, file: UploadFile):
        # Extraemos la extensión del archivo (ej. ".csv")
        try:
            extension = f".{file.filename.split('.')[-1].lower()}"
        
            if extension not in self.formatos_validos:
                # Si no es un formato válido, lanzamos un error que detiene el proceso
                raise ValueError(f"Formato no válido. Solo se permiten archivos {self.formatos_validos}")

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
        return True

    def validar_tamano(self, file: UploadFile):
        # FastAPI guarda el tamaño en bytes. Convertimos nuestros 50MB a bytes.
        tamano_max_bytes = self.tamano_max_mb * 1024 * 1024
        
        if file.size == 0:
            raise ValueError("El archivo está completamente vacío.")
            
        if file.size > tamano_max_bytes:
            raise ValueError(f"El archivo pesa demasiado. El límite es {self.tamano_max_mb} MB.")
            
        return True

    def validar_estructura(self, file: UploadFile):
        # Leemos solo un pedacito del archivo con Pandas para ver si está corrupto
        try:
            extension = f".{file.filename.split('.')[-1].lower()}"
            
            if extension == '.csv':
                # Intentamos leer solo 5 filas para no saturar la memoria RAM
                pd.read_csv(file.file, nrows=5)
            elif extension == '.xlsx':
                pd.read_excel(file.file, nrows=5)

            file.file.seek(0)
            
        except Exception as e:
            # Si ocurre cualquier error (archivo ilegible, dañado, columnas rotas)
            file.file.seek(0)
            raise ValueError(f"El archivo está dañado o su estructura no es válida. Detalle: {str(e)}")
            
        return True

    def get_resultado(self, file: UploadFile) -> bool:
        # Este método orquesta todo. Si una validación falla, lanza el error.
        # Si todas pasan, devuelve True.
        self.valida_formato(file)
        self.validar_tamano(file)
        self.validar_estructura(file)
        
        return True

class ControladorCarga:
    pass
