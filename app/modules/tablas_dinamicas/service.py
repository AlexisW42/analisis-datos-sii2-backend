import pandas as pd
import numpy as np
from typing import List, Dict, Any

class ValidadorSeleccion:

    def __init__(self):
        self.combinacion_valida: bool = True
        self.mensaje_error: str = ""

    def validar_combinacion(self, df: pd.DataFrame, filas: List[str], columnas: List[str], valor: str, funcion: str) -> bool:
        
        # EXCEPCIÓN 1: Obligar a que exista al menos una fila (Respaldo al Frontend)
        if not filas:
            self.mensaje_error = "Debe seleccionar al menos una variable en 'Dimensiones de Fila'."
            self.combinacion_valida = False
            return False

        # 0. Verificar que la función de agregación exista (AGREGAMOS 'median')
        funciones_validas = ['sum', 'mean', 'count', 'max', 'min', 'median']
        if funcion not in funciones_validas:
            self.mensaje_error = f"La función '{funcion}' no es válida. Opciones permitidas: {funciones_validas}"
            self.combinacion_valida = False
            return False

        todas_variables = filas + columnas + [valor]
        
        # 0.5 Verificar que no existan columnas duplicadas en el dataset original
        if df.columns.duplicated().any():
            columnas_duplicadas = list(set(df.columns[df.columns.duplicated()]))
            self.mensaje_error = f"El archivo cargado tiene columnas con nombres duplicados: {columnas_duplicadas}. Por favor, limpie el CSV y vuelva a cargarlo."
            self.combinacion_valida = False
            return False

        # 1. Verificar que todas las variables existan en el DataFrame
        for var in todas_variables:
            if var not in df.columns:
                self.mensaje_error = f"La variable '{var}' no existe en el dataset."
                self.combinacion_valida = False
                return False

        # 2. Verificar coherencia matemática (AGREGAMOS 'median' como operación estricta de números)
        es_numerica = pd.api.types.is_numeric_dtype(df[valor])
        funciones_matematicas = ['sum', 'mean', 'median'] 
        
        if not es_numerica and funcion in funciones_matematicas:
            self.mensaje_error = f"No puedes calcular '{funcion}' sobre '{valor}' porque contiene texto. Usa 'count'."
            self.combinacion_valida = False
            return False

        # 3. Verificar colisión de ejes (La misma variable en filas y columnas)
        interseccion = set(filas).intersection(set(columnas))
        if interseccion:
            variable_repetida = list(interseccion)[0]
            self.mensaje_error = f"Colisión detectada: La variable '{variable_repetida}' no puede estar en filas y columnas al mismo tiempo."
            self.combinacion_valida = False
            return False

        # 4. Verificar límite de procesamiento
        if len(df) > 100000:
            self.mensaje_error = "El volumen de datos excede el límite de 100,000 registros permitidos para generar la tabla en tiempo real. Se requiere procesamiento en segundo plano."
            self.combinacion_valida = False
            return False

        self.combinacion_valida = True
        return True

class MotorPivot:
    def __init__(self):
        self.procesando: bool = False

    def pivotear_dataset(self, df: pd.DataFrame, filas: List[str], columnas: List[str], valor: str, funcion: str) -> List[Dict[str, Any]]:
        self.procesando = True
        
        agg_map = {
            'sum': np.sum,
            'mean': np.mean,
            'median': np.median,
            'count': pd.Series.nunique,
            'max': np.max,
            'min': np.min
        }
        
        func = agg_map.get(funcion, 'count')

        try:
            # Reemplazamos los nulos temporalmente en las categorías
            df[filas + columnas] = df[filas + columnas].fillna("(En blanco)")

            # ¡El corazón del CU06!
            tabla_pivot = pd.pivot_table(
                df,
                values=valor,
                index=filas,
                columns=columnas if columnas else None,
                aggfunc=func
                # ELIMINAMOS el fill_value=0 de aquí para evitar el choque de tipos
            )

            tabla_plana = tabla_pivot.reset_index()

            # =========================================================
            # NUEVO: Rellenado Inteligente de Nulos (Anti-Choque de Tipos)
            # =========================================================
            for col in tabla_plana.columns:
                if pd.api.types.is_numeric_dtype(tabla_plana[col]):
                    # Si la columna es matemática, los vacíos son ceros
                    tabla_plana[col] = tabla_plana[col].fillna(0)
                else:
                    # Si la columna es texto, los vacíos son cadenas vacías
                    tabla_plana[col] = tabla_plana[col].fillna("")

            # =========================================================
            # ¡LA SOLUCIÓN DEFINITIVA AL MULTIINDEX!
            # =========================================================
            nuevas_columnas = []
            
            for col in tabla_plana.columns.values:
                if isinstance(col, tuple):
                    nombre_aplanado = " - ".join([str(c) for c in col if str(c) != ""])
                    nuevas_columnas.append(nombre_aplanado if nombre_aplanado else str(col))
                else:
                    nuevas_columnas.append(str(col))
                    
            tabla_plana.columns = nuevas_columnas

            self.procesando = False
            return tabla_plana.to_dict(orient="records")

        except Exception as e:
            self.procesando = False
            error_str = str(e)
            
            if "not 1-dimensional" in error_str:
                raise ValueError("Error de estructura: La variable seleccionada contiene datos corruptos o el nombre de la columna está duplicado en el dataset. Verifique su archivo.")
            
            raise ValueError(f"Error al procesar la tabla dinámica: {error_str}")

class ServicioPivot:
    def __init__(self):
        self.validador = ValidadorSeleccion()
        self.motor = MotorPivot()

    def generar_tablas_dinamicas(self, df: pd.DataFrame, configuracion: dict) -> Dict[str, Any]:
        filas = configuracion.get("filas", [])
        columnas = configuracion.get("columnas", [])
        valor = configuracion.get("valores")
        funcion = configuracion.get("funcion_agregacion")

        # 1. Validar
        es_valido = self.validador.validar_combinacion(df, filas, columnas, valor, funcion)
        if not es_valido:
            raise ValueError(self.validador.mensaje_error)

        # 2. Generar
        datos = self.motor.pivotear_dataset(df, filas, columnas, valor, funcion)

        # 3. Validar si quedó vacía
        if not datos:
            raise ValueError("La combinación seleccionada no arrojó ningún resultado válido.")

        return datos