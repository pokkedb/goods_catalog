from sqlalchemy import Integer, String, Float, Text, ForeignKey, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

PRODUCT_CATEGORIES = [
    "スリーブ＆カバー", "バインダー＆ファイル", "リフィル",
    "収納ケース", "フレーム", "推し活グッズ", "デコ素材", "その他",
]


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)

    brand_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("brands.id"), nullable=True)
    maker_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("makers.id"), nullable=True)
    jan_code: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # unit_price は GENERATED ALWAYS AS ... VIRTUAL 列。Computed()でマークしないとSQLAlchemyが
    # INSERT文にこの列を含めてしまい、SQLiteが「生成列にINSERTできない」とエラーになる
    unit_price: Mapped[float | None] = mapped_column(
        Float, Computed("CASE WHEN quantity > 0 THEN ROUND(CAST(price AS REAL) / quantity, 2) END", persisted=False)
    )
    pocket_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # pocket_unit_price も GENERATED ALWAYS AS ... VIRTUAL 列。同上の理由でComputed()が必要
    pocket_unit_price: Mapped[float | None] = mapped_column(
        Float, Computed("CASE WHEN pocket_count > 0 THEN ROUND(CAST(price AS REAL) / pocket_count, 2) END", persisted=False)
    )

    outer_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_depth_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_height2_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    spine_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_depth_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_height2_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pocket_inner_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pocket_inner_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    thickness_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    free_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    concerns: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    blog_url: Mapped[str | None] = mapped_column(String, nullable=True)
    micosblog_notion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    my_block: Mapped[str | None] = mapped_column(Text, nullable=True)
    shortcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_url: Mapped[str | None] = mapped_column(String, nullable=True)
    double_sided_check: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generate_flag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    brand = relationship("Brand", back_populates="products")
    maker = relationship("Maker", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    features = relationship("ProductFeature", back_populates="product", cascade="all, delete-orphan")
    sleeve_cover = relationship("SleeveCover", back_populates="product", uselist=False, cascade="all, delete-orphan")
    binder_file = relationship("BinderFile", back_populates="product", uselist=False, cascade="all, delete-orphan")
    refill = relationship("Refill", back_populates="product", uselist=False, cascade="all, delete-orphan")
    frame = relationship("Frame", back_populates="product", uselist=False, cascade="all, delete-orphan")
    oshi_goods = relationship("OshiGoods", back_populates="product", uselist=False, cascade="all, delete-orphan")
    irelu_product = relationship("IreluProduct", back_populates="product", uselist=False, cascade="all, delete-orphan")

    def __str__(self):
        return f"{self.name}（{self.category}）"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="images")

    def __str__(self):
        return f"画像#{self.sort_order} ({self.url})"


class ProductFeature(Base):
    __tablename__ = "product_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    group_no: Mapped[int] = mapped_column(Integer, nullable=False)
    tag: Mapped[str] = mapped_column(String, nullable=False)

    product = relationship("Product", back_populates="features")

    def __str__(self):
        return self.tag
