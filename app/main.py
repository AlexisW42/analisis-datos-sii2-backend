from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.modules.carga.router import router as carga_router

# Importar routers
from app.modules.usuarios.router import router as usuarios_router

# Crear las tablas en la BD (Nota: Considerar usar Alembic en el futuro)
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(usuarios_router)
app.include_router(carga_router)

@app.get("/")
def read_root():
    return {"message": "Inicio"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/datos")
def obtener_datos():
    return {
        "status": "success",
        "proyecto": "Análisis de Datos SII2",
        "tecnologias": ["Next.js", "FastAPI", "Docker"],
        "registros": [
            {"id": 1, "nombre": "Métrica A", "valor": 95.4},
            {"id": 2, "nombre": "Métrica B", "valor": 88.1}
        ]
    }

@app.get("/api/db-test")
def test_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "success", "message": "Conexión a la base de datos exitosa"}
    except Exception as e:
        return {"status": "error", "message": str(e)}