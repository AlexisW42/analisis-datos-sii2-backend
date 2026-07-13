import pandas as pd
import numpy as np
from typing import List, Dict, Any

class ValidadorSeleccion:

    def __init__(self):
        self.combinacion_valida: bool = True
        self.mensaje_error: str = ""

    def validar_combinacion(self, df: pd.DataFrame, filas: List[str], columnas: List[str], valor: str, funcion: str) -> bool:
        # 0. Verificar que la función de agregación exista
        funciones_validas = ['sum', 'mean', 'count', 'max', 'min']
        if funcion not in funciones_validas:
            self.mensaje_error = f"La función '{funcion}' no es válida. Opciones permitidas: {funciones_validas}"
            self.combinacion_valida = False
            return False

        todas_variables = filas + columnas + [valor]
        
        # 1. Verificar que todas las variables existan en el DataFrame
        for var in todas_variables:
            if var not in df.columns:
                self.mensaje_error = f"La variable '{var}' no existe en el dataset."
                self.combinacion_valida = False
                return False

        # 2. Verificar coherencia matemática
        es_numerica = pd.api.types.is_numeric_dtype(df[valor])
        funciones_matematicas = ['sum', 'mean']
        
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

        # 4. Verificar límite de procesamiento (Prevenir que el servidor colapse)
        # Limitamos el procesamiento síncrono a 100,000 filas para este ejemplo.
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
        """
        Utiliza Pandas para construir la tabla dinámica.
        """
        self.procesando = True
        
        # Mapeo de la función en string a la función real de Pandas/Numpy
        agg_map = {
            'sum': np.sum,
            'mean': np.mean,
            'count': pd.Series.nunique, # Cuenta valores únicos
            'max': np.max,
            'min': np.min
        }
        
        func = agg_map.get(funcion, 'count')

        try:
            # Reemplazamos los nulos temporalmente en las categorías para que no desaparezcan
            df[filas + columnas] = df[filas + columnas].fillna("(En blanco)")

            # ¡El corazón del CU06!
            tabla_pivot = pd.pivot_table(
                df,
                values=valor,
                index=filas,
                columns=columnas if columnas else None,
                aggfunc=func,
                fill_value=0 # Rellena vacíos con 0
            )

            # Pandas devuelve un MultiIndex complejo. Lo aplanamos para que FastAPI
            # lo pueda convertir a JSON fácilmente para tu compañero de Frontend.
            tabla_plana = tabla_pivot.reset_index()

            self.procesando = False
            return tabla_plana.to_dict(orient="records")

        except Exception as e:
            self.procesando = False
            raise ValueError(f"Error al procesar la tabla dinámica: {str(e)}")

class ServicioPivot:
    def __init__(self):
        self.validador = ValidadorSeleccion()
        self.motor = MotorPivot()

    def generar_tablas_dinamicas(self, df: pd.DataFrame, configuracion: dict) -> Dict[str, Any]:
        """
        Orquesta el Validador y el Motor.
        """
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

        # 3. Validar si quedó vacía (Excepción 3 sugerida)
        if not datos:
            raise ValueError("La combinación seleccionada no arrojó ningún resultado válido.")

        return datos