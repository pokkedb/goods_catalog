"""
固有列を持たないカテゴリ（収納ケース／デコ素材／その他）は専用テーブルを持たず、
products.category で判別する設計（Phase 0調査で確定）。
schema.sql に用意済みのロールアップ再現VIEWをそのまま閲覧用モデルとしてマッピングする。
SQLiteのVIEWは書き込み不可のため、対応するSQLAdmin側もread-only（一覧・詳細のみ）にする。
"""
from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class StorageView(Base):
    __tablename__ = "storages_view"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outer_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_depth_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    inner_depth_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    maker_name: Mapped[str | None] = mapped_column(String, nullable=True)


class DecoMaterialView(Base):
    __tablename__ = "deco_materials_view"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    jan_code: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outer_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String, nullable=True)
    maker_name: Mapped[str | None] = mapped_column(String, nullable=True)


class OtherView(Base):
    __tablename__ = "others_view"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    jan_code: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outer_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    outer_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    maker_name: Mapped[str | None] = mapped_column(String, nullable=True)
