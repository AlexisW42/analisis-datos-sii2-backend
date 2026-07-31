import os
import pytest

# Usar directorio local para almacenamiento en pruebas para evitar PermissionError
os.environ["DATASETS_STORAGE_DIR"] = "./test_storage"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# Usamos una base de datos SQLite en memoria para no afectar los datos reales de PostgreSQL.
# Esta es una buena práctica para las pruebas CAATs ya que las pruebas deben ser repetibles.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    # Crea todas las tablas en SQLite al inicio de la sesión de pruebas
    Base.metadata.create_all(bind=engine)
    yield engine
    # Destruye las tablas al finalizar
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db(db_engine):
    # Crea una conexión y una transacción por cada prueba, para aislar los tests entre sí
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db):
    # Sobreescribimos get_db de FastAPI para que use nuestra base de datos en memoria
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
