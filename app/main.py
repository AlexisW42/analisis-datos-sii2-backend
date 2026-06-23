from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.modules.carga.router import router as carga_router

from app.core.database import get_db
from app.core.config import settings
from app.modules.usuarios.router import router as usuarios_router
from app.modules.perfilado.router import router as perfilado_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion de routers
app.include_router(usuarios_router)
app.include_router(carga_router)
app.include_router(perfilado_router)

@app.get("/")
def read_root():
    return {"message": "Inicio"}

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
