from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    products = relationship("Product", back_populates="brand")

    def __str__(self):
        return self.name


class Maker(Base):
    __tablename__ = "makers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    products = relationship("Product", back_populates="maker")

    def __str__(self):
        return self.name
