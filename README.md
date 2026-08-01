# Plataforma de Análisis de Datos SII2 - Backend

Este repositorio contiene el backend de la plataforma de Análisis de Datos SII2. Procesa y analiza datasets (CSV y Excel) aplicando cálculos estadísticos, perfilado de datos y correlaciones matemáticas, exponiendo los resultados mediante una API REST protegida.

## Arquitectura y Tecnologías

Construí este backend sobre **Python 3** utilizando las siguientes tecnologías principales:

- **FastAPI:** Sirve como el framework web principal para exponer los endpoints de forma rápida y asíncrona.
- **PostgreSQL:** Actúa como el motor de base de datos relacional primario donde almaceno los metadatos de los archivos y los registros de los usuarios.
- **SQLAlchemy & Alembic:** Manejan el ORM (Mapeo Objeto-Relacional) y las migraciones de la base de datos respectivamente.
- **Pandas & NumPy:** Ejecutan la carga pesada del análisis matemático, perfilado y correlación de los datos.
- **JWT & Bcrypt:** Protegen la aplicación mediante tokens de acceso y encriptación de contraseñas.
- **Docker & Docker Compose:** Contenerizan la aplicación junto con su base de datos para facilitar su despliegue y desarrollo.

## Despliegue y Construcción

Para levantar todo el proyecto y su base de datos, usa Docker Compose. El archivo de configuración `docker-compose.yml` orquesta los contenedores.

1. Abre tu terminal en la raíz del proyecto.
2. Ejecuta este comando para construir y encender la aplicación en segundo plano:

```bash
docker-compose up -d --build
```

El servidor de la API quedará disponible en `http://localhost:8000`. 
*(Docker inicializará la base de datos y Alembic correrá las migraciones automáticamente).*

---

## Guía de Pruebas CAATs (Auditoría del Sistema)

Las pruebas automatizadas validan los controles de seguridad y exactitud del procesamiento de los datos. Sigue estos pasos para ejecutarlas.

### Opción 1: Ejecutar con Docker (Recomendado)

Usa esta opción si tú o tus compañeros ya tienen los contenedores funcionando.

1. Abre tu terminal.
2. Verifica que los contenedores del proyecto estén encendidos.
3. Ejecuta el siguiente comando exactamente como aparece:

```bash
docker exec sii2_backend python -m pytest tests/caats/ -v
```

4. Lee el reporte verde en la pantalla. Este reporte confirma que las pruebas pasaron exitosamente.

### Opción 2: Ejecutar de manera local (Sin Docker)

Usa esta opción si prefieres probar directamente en tu entorno virtual local.

1. Abre tu terminal en la carpeta principal del backend.
2. Activa tu entorno virtual con el siguiente comando:

```bash
source venv/bin/activate
```

3. Ejecuta el siguiente comando para iniciar las pruebas:

```bash
PYTHONPATH=. pytest tests/caats/ -v
```

4. Revisa los resultados en la pantalla para confirmar que todos los controles funcionan correctamente.
