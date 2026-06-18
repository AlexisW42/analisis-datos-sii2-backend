from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.usuarios import schemas, service, models
from app.core.config import settings

router = APIRouter(tags=["Usuarios y Autenticación"])

@router.post("/auth/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = service.get_user_by_email(db, email=form_data.username)
    if not user or not service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = service.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

from typing import List

@router.get("/usuarios/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.Usuario = Depends(service.get_current_user)):
    return current_user

@router.post("/usuarios/admin/create", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_admin(user: schemas.UserCreate, db: Session = Depends(get_db), admin_user: models.Usuario = Depends(service.verificar_admin)):
    db_user = service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    return service.create_user(db=db, user=user)

@router.get("/usuarios/admin/lista-usuarios", response_model=List[schemas.UserResponse])
def listar_usuarios_para_admin(db: Session = Depends(get_db), admin_user: models.Usuario = Depends(service.verificar_admin)):
    return db.query(models.Usuario).all()
