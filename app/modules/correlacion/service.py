import pandas as pd
from scipy.stats import pearsonr 
from typing import List, Dict, Any

class SelectorVariables:
    def __init__(self):
        # Atributos inicializados vacíos, listos para ser llenados
        self.columnas_numericas: List[str] = []
        self.recuento_faltantes: Dict[str, int] = {}

    def filtrar_variables_numericas(self, df: pd.DataFrame) -> List[str]:
        """
        Analiza el DataFrame y extrae únicamente las columnas de tipo cuantitativo.
        Cumple con el Proceso Obligatorio 2.
        """
        # Pandas hace el trabajo pesado: select_dtypes filtra nativamente números (int, float)
        df_numerico = df.select_dtypes(include='number')
        
        # Extraemos los nombres de las columnas y los guardamos en el atributo de la clase
        self.columnas_numericas = df_numerico.columns.tolist()
        
        return self.columnas_numericas

    def verificar_cantidad_minima(self, columnas: List[str]) -> bool:
        """
        Valida que existan al menos 2 variables numéricas para poder correlacionar.
        """
        # Una matriz de correlación necesita como mínimo 2 variables (X e Y)
        return len(columnas) >= 2

    def detectar_datos_faltantes(self, df: pd.DataFrame, columnas: List[str]) -> Dict[str, int]:
        """
        Examina y cuenta los valores nulos o vacíos en las columnas seleccionadas.
        """
        # 1. Filtramos el DataFrame para mirar solo las columnas numéricas
        df_filtrado = df[columnas]
        
        # 2. isna().sum() cuenta los nulos, y to_dict() lo convierte al formato de diccionario de Python
        nulos_por_columna = df_filtrado.isna().sum().to_dict()
        
        # 3. Guardamos el resultado en el atributo de la clase
        self.recuento_faltantes = nulos_por_columna
        
        return self.recuento_faltantes



class MotorCorrelacion:
    def __init__(self, metodo_calculo: str = "pearson"):
        self.metodo_calculo = metodo_calculo
        self.matriz_coeficientes: Dict[str, Dict[str, float]] = {}
        self.matriz_significancia: Dict[str, Dict[str, float]] = {}

    def calcular_matriz(self, df: pd.DataFrame, variables: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Calcula la matriz de correlación completa entre las variables indicadas.
        """
        # Filtramos el DataFrame para usar solo las variables numéricas validadas
        df_filtrado = df[variables]
        
        # Calculamos la correlación y convertimos el DataFrame resultante a un diccionario
        matriz_df = df_filtrado.corr(method=self.metodo_calculo)
        
        # Redondeamos a 4 decimales para mayor limpieza y lo guardamos
        self.matriz_coeficientes = matriz_df.round(4).to_dict()
        
        return self.matriz_coeficientes

    def calcular_significancia(self, df: pd.DataFrame, variables: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Calcula el P-valor para determinar si la correlación es estadísticamente significativa.
        """
        # Limpiamos filas con nulos temporalmente solo para este cálculo matemático
        df_limpio = df[variables].dropna()
        
        # Inicializamos el diccionario bidimensional
        self.matriz_significancia = {v: {} for v in variables}
        
        for v1 in variables:
            for v2 in variables:
                if v1 == v2:
                    self.matriz_significancia[v1][v2] = 0.0 # La variable contra sí misma
                else:
                    # Calculamos el P-valor usando Scipy
                    _, p_valor = pearsonr(df_limpio[v1], df_limpio[v2])
                    self.matriz_significancia[v1][v2] = round(p_valor, 4)
                    
        return self.matriz_significancia

    def obtener_coeficiente(self, var1: str, var2: str) -> float:
        """
        Consulta la relación específica entre un par de variables en la matriz ya calculada.
        """
        try:
            return self.matriz_coeficientes[var1][var2]
        except KeyError:
            raise ValueError(f"Las variables {var1} y/se {var2} no existen en la matriz calculada.")




class VisualizadorMatriz:
    def __init__(self, umbral_fuerte: float = 0.7):
        # 0.7 es el estándar estadístico para una correlación lineal fuerte
        self.umbral_fuerte = umbral_fuerte 
        self.relaciones_claves: List[Dict[str, Any]] = []

    def limpiar(self):
        """Restablece los datos de la clase para un nuevo análisis."""
        self.relaciones_claves = []

    def generar_vista_matriz(self, matriz: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        Transforma el diccionario bidimensional en una lista plana de coordenadas (x, y, valor).
        Esto es exactamente lo que piden las librerías de FrontEnd para dibujar mapas de calor.
        """
        vista_plana = []
        for var_y, correlaciones in matriz.items():
            for var_x, coeficiente in correlaciones.items():
                vista_plana.append({
                    "id_x": var_x,
                    "id_y": var_y,
                    "valor": coeficiente
                })
        return vista_plana

    def filtrar_relaciones_fuertes(self, matriz: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        Escanea la matriz buscando coeficientes (positivos o negativos) que superen el umbral.
        Evita duplicados (A-B es lo mismo que B-A) y evita comparar una variable consigo misma (A-A).
        """
        self.limpiar()
        pares_procesados = set()

        for var1, correlaciones in matriz.items():
            for var2, coeficiente in correlaciones.items():
                # Creamos un identificador único para el par ordenándolo alfabéticamente
                par_id = tuple(sorted([var1, var2]))
                
                # Ignoramos si es la misma variable (coef = 1.0) o si ya procesamos este par
                if var1 == var2 or par_id in pares_procesados:
                    continue
                
                # Usamos abs() porque una correlación de -0.8 es igual de fuerte que una de 0.8
                if abs(coeficiente) >= self.umbral_fuerte:
                    self.relaciones_claves.append({
                        "variable_1": var1,
                        "variable_2": var2,
                        "coeficiente": coeficiente,
                        "tipo": "Directa" if coeficiente > 0 else "Inversa"
                    })
                
                pares_procesados.add(par_id)
                
        # Ordenamos la lista de la relación más fuerte a la más débil
        self.relaciones_claves.sort(key=lambda x: abs(x["coeficiente"]), reverse=True)
        return self.relaciones_claves

    def identificar_variables_claves(self) -> List[str]:
        """
        Analiza las relaciones fuertes y determina cuáles variables aparecen con más frecuencia.
        Estas son las variables con mayor influencia general en el Dataset.
        """
        if not self.relaciones_claves:
            return []
            
        conteo_frecuencia = {}
        for relacion in self.relaciones_claves:
            v1, v2 = relacion["variable_1"], relacion["variable_2"]
            conteo_frecuencia[v1] = conteo_frecuencia.get(v1, 0) + 1
            conteo_frecuencia[v2] = conteo_frecuencia.get(v2, 0) + 1
            
        # Ordenamos las variables por la cantidad de relaciones fuertes que tienen
        variables_ordenadas = sorted(conteo_frecuencia.items(), key=lambda x: x[1], reverse=True)
        return [var[0] for var in variables_ordenadas]


class ServicioCorrelacion:
    def __init__(self):
        # Instanciamos los componentes internos según tu Diagrama de Clases
        self.selector = SelectorVariables()
        self.motor = MotorCorrelacion()
        self.visualizador = VisualizadorMatriz()
        self.configuracion_actual: Dict[str, Any] = {}

    def aplicar_tratamiento_nulos(self, df: pd.DataFrame, variables: List[str], estrategia: str) -> pd.DataFrame:
        """
        Maneja el Flujo Alterno 2: Aplica el tratamiento configurado para los nulos.
        """
        df_copia = df[variables].copy()
        
        if estrategia == "eliminar_filas":
            # Borra la fila completa si tiene algún nulo en las variables seleccionadas
            return df_copia.dropna()
            
        elif estrategia == "imputar_promedio":
            # Llena los espacios vacíos con el promedio matemático de esa columna
            return df_copia.fillna(df_copia.mean())
            
        # Si la estrategia es "ignorar", Pandas manejará la omisión nativamente en corr()
        return df_copia

    def generar_matriz_correlacion(self, df: pd.DataFrame, estrategia_nulos: str = "ignorar", metodo: str = "pearson") -> Dict[str, Any]:
        """
        Orquesta todo el proceso del CU05. Cumple con todos los Procesos Obligatorios 
        y gestiona las excepciones.
        """
        # Guardamos la configuración de la sesión actual
        self.configuracion_actual = {
            "estrategia_nulos": estrategia_nulos,
            "metodo": metodo
        }
        self.motor.metodo_calculo = metodo

        # 1. Filtrar variables numéricas (Proceso Obligatorio 2)
        columnas_num = self.selector.filtrar_variables_numericas(df)

        # 2. Verificar cantidad mínima (Manejo del Flujo Alterno 1)
        if not self.selector.verificar_cantidad_minima(columnas_num):
            raise ValueError("No existen suficientes variables numéricas para realizar el análisis de correlación (Mínimo requerido: 2).")

        # 3. Detectar datos faltantes (Preparación para el Flujo Alterno 2)
        faltantes = self.selector.detectar_datos_faltantes(df, columnas_num)
        tiene_nulos = any(cantidad > 0 for cantidad in faltantes.values())

        # Aplicamos el tratamiento configurado para los nulos
        df_listo = self.aplicar_tratamiento_nulos(df, columnas_num, estrategia_nulos)

        # 4. Calcular Coeficientes y Significancia (Proceso Obligatorio 3)
        matriz_num = self.motor.calcular_matriz(df_listo, columnas_num)
        self.motor.calcular_significancia(df_listo, columnas_num)

        # 5. Construir formato visual para el Heatmap (Proceso Obligatorio 4)
        matriz_visual = self.visualizador.generar_vista_matriz(matriz_num)

        # 6. Resaltar Relaciones Fuertes (Proceso Obligatorio 5)
        relaciones_fuertes = self.visualizador.filtrar_relaciones_fuertes(matriz_num)

        # 7. Identificar Variables Claves (Proceso Obligatorio 6)
        variables_claves = self.visualizador.identificar_variables_claves()

        # Construimos el aviso de omisión si el usuario decidió ignorar los nulos
        aviso_omision = ""
        if tiene_nulos and estrategia_nulos == "ignorar":
            aviso_omision = f"Informa: Se detectaron nulos en el dataset {faltantes}. Los valores faltantes fueron omitidos del cálculo."

        # Retornamos el paquete estructurado exacto que va a requerir el endpoint de FastAPI
        return {
            "configuracion": self.configuracion_actual,
            "aviso_omision": aviso_omision,
            "matriz_calor": matriz_visual,
            "relaciones_fuertes": relaciones_fuertes,
            "variables_claves": variables_claves,
            "matriz_significancia": self.motor.matriz_significancia
        }

