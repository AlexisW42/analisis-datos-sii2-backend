from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

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