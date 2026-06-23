from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.database import get_db
from app.modules.usuarios import models, schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def verify_password(plain_password, hashed_password):
    """
    Compara una contrasena en texto plano contra su hash almacenado.
    """
    # compararlos. 
    # El hash almacenado ya contiene la sal necesaria.
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def get_password_hash(password):
    """
    Genera un hash seguro para una contrasena nueva.

    Cada llamada usa `bcrypt.gensalt()`, lo que produce una sal diferente y hace
    que dos usuarios con la misma contrasena tengan hashes distintos en la base
    de datos.
    """
    
    # El resultado de bcrypt es bytes; se decodifica a texto para guardarlo
    # facilmente en una columna string de la base de datos.
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

def get_user_by_email(db: Session, email: str):
    """
    Busca un usuario por email y devuelve la primera coincidencia.

    Se usa como funcion auxiliar tanto en login como en registro y validacion de
    tokens. Si no existe un usuario con ese email, SQLAlchemy devuelve None.
    """
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """
    Crea un usuario desde un flujo administrativo.

    Recibe `UserCreate`, por lo que puede respetar el rol indicado por un
    administrador. Antes de persistir, transforma la contrasena recibida en un
    hash seguro.
    """
    # Nunca se guarda `user.password` directamente; primero se convierte en un
    # hash bcrypt para que la base de datos no contenga contrasenas legibles.
    hashed_password = get_password_hash(user.password)

    # Se construye la entidad SQLAlchemy que representa la fila de la tabla de
    # usuarios. El rol proviene del esquema recibido, validado previamente por
    # Pydantic.
    db_user = models.Usuario(
        email=user.email,
        hashed_password=hashed_password,
        rol=user.rol
    )

    # `add` marca la instancia para insercion, `commit` confirma la transaccion
    # y `refresh` recarga el objeto con los valores generados por la base de
    # datos, como el `id`.
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def register_user(db: Session, user: schemas.UserRegister):
    """
    Registra un usuario final con rol fijo `user`.

    Este flujo corresponde al registro publico. A diferencia de `create_user`,
    no acepta rol desde el cliente para impedir que alguien se registre como
    administrador por su cuenta.
    """
    # Se aplica el mismo mecanismo de hashing usado por la creacion
    # administrativa, manteniendo una unica forma de proteger contrasenas.
    hashed_password = get_password_hash(user.password)

    # El rol se asigna explicitamente como texto `user`; asi se ignora cualquier
    # intento externo de elevar permisos durante el registro publico.
    db_user = models.Usuario(
        email=user.email,
        hashed_password=hashed_password,
        rol="user"
    )

    # Persiste el nuevo usuario y refresca la instancia para devolver un objeto
    # actualizado al router.
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Crea un JWT firmado con los datos recibidos y una fecha de expiracion.

    `data` suele incluir el claim `sub`, que identifica al usuario autenticado.
    El token se firma con la clave secreta y el algoritmo configurados en la
    aplicacion, de modo que luego pueda validarse en `get_current_user`.
    """
    # Se copia el diccionario para no modificar el objeto original que recibio
    # la funcion desde el router u otro servicio.
    to_encode = data.copy()

    # Si el llamador entrega una duracion especifica, se usa esa. De lo
    # contrario, se aplica el tiempo por defecto definido en settings.
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # El claim `exp` es estandar en JWT y permite que la libreria rechace tokens
    # vencidos durante la decodificacion.
    to_encode.update({"exp": expire})

    # El token queda firmado; cualquier cambio posterior en su contenido hara
    # que la verificacion falle al decodificarlo.
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Valida el token Bearer de la peticion y devuelve el usuario autenticado.

    Esta funcion esta pensada para usarse como dependencia en rutas protegidas.
    Si el token no existe, esta vencido, esta mal firmado o apunta a un usuario
    inexistente, se responde con HTTP 401.
    """
    # Se prepara una misma excepcion para todos los fallos de autenticacion. Asi
    # no se filtran detalles internos sobre si fallo la firma, la expiracion, el
    # formato del token o la existencia del usuario.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica y valida la firma del JWT usando la misma clave y algoritmo
        # usados al crearlo. PyJWT tambien valida `exp` si el token lo incluye.
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # El email se espera en el claim `sub`, definido al crear el token en el
        # login. Debe existir y ser texto para poder buscar al usuario.
        email = payload.get("sub")
        if email is None or not isinstance(email, str):
            raise credentials_exception

        # TokenData centraliza la forma interna en la que representamos los
        # datos extraidos del token.
        token_data = schemas.TokenData(email=email)
    except jwt.PyJWTError:
        # Cualquier error propio de PyJWT se convierte en el mismo 401 generico.
        raise credentials_exception

    # Defensa adicional: aunque ya se valido arriba, se mantiene la verificacion
    # para asegurar que no se busque un usuario con email nulo.
    if token_data.email is None:
        raise credentials_exception

    # El token solo prueba identidad si el usuario asociado sigue existiendo en
    # la base de datos. Si fue eliminado, el token deja de ser aceptado.
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

def verificar_admin(current_user: models.Usuario = Depends(get_current_user)):
    """
    Verifica que el usuario autenticado tenga rol de administrador.

    Se usa como dependencia en endpoints administrativos. Primero reutiliza
    `get_current_user` para autenticar la peticion y despues aplica la regla de
    autorizacion basada en el campo `rol`.
    """
    # Un usuario autenticado pero sin rol `admin` recibe 403: la identidad es
    # valida, pero no tiene permiso para ejecutar la accion solicitada.
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador para realizar esta acción."
        )

    # Devolver el usuario permite que el endpoint, si lo necesita, conozca que
    # administrador realizo la operacion.
    return current_user
