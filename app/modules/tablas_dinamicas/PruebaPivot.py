import pandas as pd

# Asegúrate de que esta ruta coincida con la ubicación real de tu service.py
from app.modules.tablas_dinamicas.service import ServicioPivot

def ejecutar_prueba():
    print("Iniciando prueba de Tablas Dinámicas (Mocking)...")

    # 1. Creamos un Dataset simulado directamente en la memoria RAM
    datos_falsos = {
        "Region": ["Norte", "Norte", "Sur", "Sur", "Norte", "Sur"],
        "Categoria": ["Electronica", "Muebles", "Electronica", "Muebles", "Electronica", "Electronica"],
        "Vendedor": ["Juan", "Ana", "Pedro", "Luis", "Juan", "Pedro"],
        "Ventas": [1500, 800, 2000, 1200, 1600, 2100]
    }
    df_mock = pd.DataFrame(datos_falsos)
    
    print("\n--- Dataset Original ---")
    print(df_mock)

    # 2. Instanciamos tu servicio
    servicio = ServicioPivot()

    # 3. Configuramos la petición: Queremos ver las ventas totales por Región (filas) y Categoría (columnas)
    configuracion = {
        "filas": ["Region"],
        "columnas": ["Categoria"],
        "valores": "Ventas",
        "funcion_agregacion": "sum"
    }

    print(f"\n--- Ejecutando Motor Pivot ---")
    print(f"Filas: {configuracion['filas']} | Columnas: {configuracion['columnas']} | Medida: {configuracion['valores']} ({configuracion['funcion_agregacion']})")

    # 4. Ejecutamos la lógica de negocio
    try:
        resultado = servicio.generar_tablas_dinamicas(df_mock, configuracion)
        print("\n--- Resultado Generado por el Backend ---")
        # Imprimimos el resultado iterando la lista para que se vea claro en consola
        for fila in resultado:
            print(fila)
            
    except Exception as e:
        print(f"\n[ERROR] La prueba falló: {e}")

if __name__ == "__main__":
    ejecutar_prueba()