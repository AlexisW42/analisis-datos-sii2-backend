import pandas as pd
import sys

# Parche para la ruta, por si lo ejecutas directamente con 'python archivo.py'
sys.path.insert(0, '/app')

from app.modules.tablas_dinamicas.service import ServicioPivot

def ejecutar_pruebas_excepciones():
    print("Iniciando batería de pruebas de EXCEPCIONES (Mocking)...")
    
    # Dataset simulado
    datos_falsos = {
        "Region": ["Norte", "Norte", "Sur", "Sur", "Norte", "Sur"],
        "Categoria": ["Electronica", "Muebles", "Electronica", "Muebles", "Electronica", "Electronica"],
        "Vendedor": ["Juan", "Ana", "Pedro", "Luis", "Juan", "Pedro"],
        "Ventas": [1500, 800, 2000, 1200, 1600, 2100]
    }
    df_mock = pd.DataFrame(datos_falsos)
    servicio = ServicioPivot()

    # Definimos los escenarios que DEBERÍAN fallar
    pruebas = [
        {
            "nombre": "Prueba 1: Variable Inexistente",
            "datos": df_mock, # Usamos el dataset normal
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Ciudad_Fantasma"], 
                "valores": "Ventas", 
                "funcion_agregacion": "sum"
            }
        },
        {
            "nombre": "Prueba 2: Error Matemático (Sumar Texto)",
            "datos": df_mock, # Usamos el dataset normal
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Categoria"], 
                "valores": "Vendedor",       
                "funcion_agregacion": "sum"
            }
        },
        {
            "nombre": "Prueba 3: Dataset sin resultados (Tabla Vacía)",
            # Simulamos un dataset que se quedó sin filas después de un filtro
            "datos": pd.DataFrame(columns=df_mock.columns), 
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Categoria"], 
                "valores": "Ventas",       
                "funcion_agregacion": "sum"
            }
        },
        {
            "nombre": "Prueba 4: Colisión de Ejes (Misma variable en fila y columna)",
            "datos": df_mock, 
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Region"], # <-- Aquí forzamos la colisión
                "valores": "Ventas", 
                "funcion_agregacion": "sum"
            }
        },
        {
            "nombre": "Prueba 5: Volumen de Datos Excesivo",
            # Simulamos un dataset gigante concatenando el mock 20,000 veces (120,000 filas)
            "datos": pd.concat([df_mock] * 20000, ignore_index=True), 
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Categoria"], 
                "valores": "Ventas",       
                "funcion_agregacion": "sum"
            }
        },
        {
            "nombre": "Prueba 6: Función de Agregación Inválida (Falla Silenciosa)",
            "datos": df_mock, 
            "configuracion": {
                "filas": ["Region"], 
                "columnas": ["Categoria"], 
                "valores": "Ventas",       
                "funcion_agregacion": "promedio_loco" # <-- Error de tipeo intencional
            }
        }
    ]

    for prueba in pruebas:
        print(f"\n--- Ejecutando {prueba['nombre']} ---")
        try:
            # Ahora le pasamos el dataset específico de cada prueba
            servicio.generar_tablas_dinamicas(prueba["datos"], prueba["configuracion"])
            print("❌ ERROR GRAVE: La prueba falló. El sistema permitió una operación inválida.")
        
        except ValueError as e:
            print(f"✅ ÉXITO: El sistema detuvo la operación y arrojó el mensaje correcto:")
            print(f"   -> {e}")

if __name__ == "__main__":
    ejecutar_pruebas_excepciones()