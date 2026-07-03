from sqlalchemy import Integer, String, Float, ForeignKey, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class GoodsCategory(Base):
    __tablename__ = "goods_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # goods_size_label は SQLite側の GENERATED ALWAYS AS ... VIRTUAL 列。Computed()でマークしないと
    # SQLAlchemyがINSERT/UPDATE文にこの列を含めてしまいSQLiteがエラーになる（products.unit_priceと同じ理由）
    goods_size_label: Mapped[str | None] = mapped_column(
        String,
        Computed(
            "'(縦' || COALESCE(CAST(height_mm AS TEXT), '') || 'mm 横' || COALESCE(CAST(width_mm AS TEXT), '') || 'mm)'",
            persisted=False,
        ),
    )

    targets = relationship(
        "GoodsCategoryTarget", back_populates="goods_category", cascade="all, delete-orphan"
    )

    def __str__(self):
        return self.name


class GoodsCategoryTarget(Base):
    __tablename__ = "goods_category_targets"

    goods_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods_categories.id"), primary_key=True
    )
    target_item: Mapped[str] = mapped_column(String, primary_key=True)

    goods_category = relationship("GoodsCategory", back_populates="targets")


class GoodsCategorySelflink(Base):
    __tablename__ = "goods_category_selflinks"

    goods_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods_categories.id"), primary_key=True
    )
    linked_goods_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods_categories.id"), primary_key=True
    )
