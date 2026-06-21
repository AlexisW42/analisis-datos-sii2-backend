from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Análisis de Datos SII2"
    DATABASE_URL: str = "postgresql://admin:adminpassword@db:5432/sii2_db"
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_URL: str = "http://localhost:3000"
    # LLM_API_KEY: str = ""
    # Agrega más configuraciones según necesites

    class Config:
        env_file = ".env"

settings = Settings()
