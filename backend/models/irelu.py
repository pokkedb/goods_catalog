from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class IreluProduct(Base):
    __tablename__ = "irelu_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    category_type: Mapped[str] = mapped_column(String, nullable=False)
    model_number: Mapped[str | None] = mapped_column(String, nullable=True)
    release_date: Mapped[str | None] = mapped_column(String, nullable=True)
    generate_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="irelu_product")
    features = relationship("IreluFeature", back_populates="irelu_product", cascade="all, delete-orphan")
    item_links = relationship("IreluItemLink", back_populates="irelu_product", cascade="all, delete-orphan")

    def __str__(self):
        return f"{self.category_type}:{self.model_number or self.id}"


class IreluFeature(Base):
    __tablename__ = "irelu_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    irelu_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("irelu_products.id"), nullable=False)
    feature_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    irelu_product = relationship("IreluProduct", back_populates="features")

    def __str__(self):
        return self.title or f"特徴{self.feature_no}"


class IreluItem(Base):
    __tablename__ = "irelu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    generate_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    item_links = relationship("IreluItemLink", back_populates="irelu_item", cascade="all, delete-orphan")

    def __str__(self):
        return self.name


class IreluItemLink(Base):
    __tablename__ = "irelu_item_links"

    irelu_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("irelu_items.id"), primary_key=True)
    irelu_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("irelu_products.id"), primary_key=True)

    irelu_item = relationship("IreluItem", back_populates="item_links")
    irelu_product = relationship("IreluProduct", back_populates="item_links")

    def __str__(self):
        return f"{self.irelu_item_id} - {self.irelu_product_id}"
