from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.usuarios import schemas, service, models
from app.core.config import settings

# Grupo de endpoints relacionados con usuarios y autenticación.
router = APIRouter(tags=["Usuarios y Autenticación"])

@router.post("/auth/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Autentica a un usuario y genera un token JWT de acceso.

    Llenamos `form_data` usando el formato estandar OAuth2 Password Flow:
    - `username`: en esta aplicacion se interpreta como el email del usuario.
    - `password`: contrasena en texto plano enviada por el cliente.

    La dependencia `get_db` entrega una sesion de base de datos por request.
    Si las credenciales son validas, se devuelve un token Bearer firmado con la
    configuracion central de seguridad.
    """
    # OAuth2PasswordRequestForm siempre expone el identificador como `username`.
    # En este proyecto ese campo representa el email con el que se registro el
    # usuario, por eso se consulta usando `form_data.username`.
    user = service.get_user_by_email(db, email=form_data.username)

    # Verificamos la existencia del usuario y la validez de la contrasena.
    # El mensaje no especifica cual dato falló para no revelar si
    # un email existe o no en la base de datos.
    if not user or not service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # El tiempo de vida del token esta definido en la configuración de la app con
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # identificamos el usuario por el email porque es el dato que
    # `get_current_user` decodifica luego para recuperar al usuario.
    access_token = service.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # La respuesta respeta el esquema `schemas.Token`: token firmado y tipo
    # Bearer, que es el formato esperado por clientes OAuth2/JWT.
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Registra usuarios finales con rol por defecto.

    Este endpoint esta pensado para alta pública de usuarios normales. Por eso
    recibe `UserRegister`, que no permite escoger rol, y delega en
    `service.register_user` la creacion con rol `user`.
    """
    
    # Antes de insertar se verifica que el email no este registrado. Esto evita
    # duplicados y permite devolver un error claro al cliente.
    db_user = service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    # El servicio se encarga de hashear la contrasena, persistir el registro y
    # refrescar la instancia antes de devolverla.
    return service.register_user(db=db, user=user)

@router.get("/usuarios/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.Usuario = Depends(service.get_current_user)):
    """
    Devuelve la informacion del usuario autenticado.

    La dependencia `get_current_user` valida el token Bearer, decodifica el JWT,
    busca el usuario asociado al email del claim `sub` y solo permite continuar
    si el token y el usuario son validos.
    """
    # No se consulta nuevamente la base de datos aqui porque la dependencia ya
    # resolvio y valido el usuario actual.
    return current_user

@router.post("/usuarios/admin/create", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_admin(user: schemas.UserCreate, db: Session = Depends(get_db), admin_user: models.Usuario = Depends(service.verificar_admin)):
    """
    Crea usuarios desde un contexto administrativo.

    A diferencia del registro publico, este endpoint recibe `UserCreate`, que
    permite definir el rol del nuevo usuario. La dependencia `verificar_admin`
    bloquea la operacion si quien hace la peticion no tiene rol de
    administrador.
    """
    # `admin_user` no se usa directamente dentro de la funcion, pero su presencia
    # como dependencia fuerza la validacion de permisos antes de ejecutar la
    # creacion del usuario.
    db_user = service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    # La creacion concreta se delega al servicio para centralizar el hash de la
    # contrasena y las operaciones de persistencia.
    return service.create_user(db=db, user=user)

@router.get("/usuarios/admin/lista-usuarios", response_model=List[schemas.UserResponse])
def listar_usuarios_para_admin(db: Session = Depends(get_db), admin_user: models.Usuario = Depends(service.verificar_admin)):
    """
    Lista todos los usuarios registrados para consumo administrativo.

    Solo un usuario autenticado con rol `admin` puede acceder a esta ruta. La
    respuesta se serializa con `UserResponse`, por lo que no se exponen campos
    sensibles como `hashed_password`.
    """
    # Igual que en el endpoint de creacion administrativa, `admin_user` existe
    # para activar la dependencia de autorizacion aunque no sea necesario usar
    # su valor dentro del cuerpo de la funcion.
    return db.query(models.Usuario).all()
