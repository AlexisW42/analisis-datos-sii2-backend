from fastapi import APIRouter

router = APIRouter(prefix="/carga", tags=["carga"])

@router.get("/")
def get_carga():
    return {"message": "Módulo de Carga (CU01)"}
