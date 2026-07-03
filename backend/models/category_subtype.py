from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class SleeveCover(Base):
    __tablename__ = "sleeve_covers"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), primary_key=True)
    sleeve_type: Mapped[str | None] = mapped_column(String, nullable=True)
    goods_category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("goods_categories.id"), nullable=True
    )

    product = relationship("Product", back_populates="sleeve_cover")
    goods_category = relationship("GoodsCategory")

    def __str__(self):
        return self.sleeve_type or "(スリーブタイプ未設定)"


class BinderFile(Base):
    __tablename__ = "binder_files"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), primary_key=True)
    file_standard: Mapped[str | None] = mapped_column(String, nullable=True)

    product = relationship("Product", back_populates="binder_file")

    def __str__(self):
        return self.file_standard or "(ファイル規格未設定)"


class Refill(Base):
    __tablename__ = "refills"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), primary_key=True)
    pocket_count_label: Mapped[str | None] = mapped_column(String, nullable=True)
    refill_standard: Mapped[str | None] = mapped_column(String, nullable=True)

    product = relationship("Product", back_populates="refill")

    def __str__(self):
        return self.pocket_count_label or "(ポケット数未設定)"


class Frame(Base):
    __tablename__ = "frames"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), primary_key=True)
    has_stand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_wall_hook: Mapped[int | None] = mapped_column(Integer, nullable=True)

    product = relationship("Product", back_populates="frame")

    def __str__(self):
        return f"スタンド:{self.has_stand} 壁掛け:{self.has_wall_hook}"


class OshiGoods(Base):
    __tablename__ = "oshi_goods"

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), primary_key=True)
    subcategory: Mapped[str | None] = mapped_column(String, nullable=True)
    has_hanging_hardware: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_charm_hole: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    product = relationship("Product", back_populates="oshi_goods")

    def __str__(self):
        return self.subcategory or "(推し活グッズカテゴリ未設定)"
