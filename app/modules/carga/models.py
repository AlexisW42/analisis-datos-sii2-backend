from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True, nullable=False)
    descripcion = Column(String, nullable=True)
    nombre_archivo = Column(String, nullable=True)
    ruta_archivo = Column(String, nullable=False)
    peso_bytes = Column(Integer, nullable=False)
    fecha_subida = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    usuario = relationship("Usuario")
    
