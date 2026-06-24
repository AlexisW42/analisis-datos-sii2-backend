from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Perfilado(Base):
    __tablename__ = "perfilado"

    id = Column(Integer, primary_key=True, index=True)
    id_dataset = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, unique=True)
    path_perfilado = Column(String, nullable=False)
    weigth_mb = Column(Float, nullable=False)

    dataset = relationship("Dataset", back_populates="perfilado")
