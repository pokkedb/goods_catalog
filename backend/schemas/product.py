from pydantic import BaseModel, field_validator

_FULLWIDTH_DIGITS = "０１２３４５６７８９"
_HALFWIDTH_DIGITS = "0123456789"
_FULLWIDTH_TO_HALFWIDTH = str.maketrans(_FULLWIDTH_DIGITS, _HALFWIDTH_DIGITS)


def normalize_digits(value: str | None) -> str | None:
    """全角数字を半角に変換する（JANコード等の数字系フィールド用）"""
    if value is None:
        return None
    return value.translate(_FULLWIDTH_TO_HALFWIDTH)


PRODUCT_CATEGORIES = [
    "スリーブ＆カバー", "バインダー＆ファイル", "リフィル",
    "収納ケース", "フレーム", "推し活グッズ", "デコ素材", "その他",
]

FEATURE_GROUP_LABELS = {
    1: "見た目", 2: "実用性", 3: "利用シーン", 4: "素材", 5: "カラー", 6: "購入対象者",
}


class ProductImageOut(BaseModel):
    id: int
    url: str
    sort_order: int

    model_config = {"from_attributes": True}


class FeatureTagOut(BaseModel):
    id: int
    group_no: int
    tag: str

    model_config = {"from_attributes": True}


class FeatureTagIn(BaseModel):
    group_no: int
    tag: str


class IreluFeatureOut(BaseModel):
    feature_no: int
    title: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class IreluFeatureIn(BaseModel):
    feature_no: int
    title: str | None = None
    description: str | None = None


# 商品本体 + カテゴリ別詳細（該当カテゴリの列だけ非nullになる。フラットに1オブジェクトへまとめて
# フロント側の条件分岐を単純にする）
class ProductBase(BaseModel):
    name: str
    category: str
    # ブランド/発売元は名前で受け取り、サーバー側で既存名に一致すればそのID・
    # なければ新規作成する（get-or-create）。新規追加をフォームから直接できるようにするため
    brand_name: str | None = None
    maker_name: str | None = None
    jan_code: str | None = None

    @field_validator("jan_code", mode="before")
    @classmethod
    def _normalize_jan_code(cls, v):
        return normalize_digits(v)
    price: int | None = None
    quantity: int | None = None
    pocket_count: int | None = None
    outer_width_mm: float | None = None
    outer_height_mm: float | None = None
    outer_depth_mm: float | None = None
    outer_height2_mm: float | None = None
    spine_width_mm: float | None = None
    inner_width_mm: float | None = None
    inner_height_mm: float | None = None
    inner_depth_mm: float | None = None
    inner_height2_mm: float | None = None
    pocket_inner_width_mm: float | None = None
    pocket_inner_height_mm: float | None = None
    thickness_mm: float | None = None
    weight_g: float | None = None
    free_description: str | None = None
    concerns: str | None = None
    reference_url: str | None = None
    double_sided_check: bool = False

    # カテゴリ別詳細（対応カテゴリ以外は無視される）
    # sleeve_type/file_standard/subcategory はDB側でCHECK制約付きのenum列のため、
    # 空文字はCHECK制約に一致せずSQLiteがエラーになる。未選択時はNoneに正規化する
    sleeve_type: str | None = None
    goods_category_id: int | None = None
    file_standard: str | None = None
    pocket_count_label: str | None = None
    refill_standard: str | None = None
    has_stand: bool | None = None
    has_wall_hook: bool | None = None
    subcategory: str | None = None
    has_hanging_hardware: bool | None = None
    has_charm_hole: bool | None = None

    @field_validator("sleeve_type", "file_standard", "subcategory", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        return v if v else None
    capacity_estimate: int | None = None


class ProductUpdate(ProductBase):
    features: list[FeatureTagIn] = []
    # irelu連携は「ブランド名がirelu」かどうかで自動的に作成/解除される（実データで1:1対応を確認済み）。
    # ここで送る品番/発売日/特徴はirelu連携時（brand_name="irelu"かつcategoryがirelu対応カテゴリの時）のみ適用される
    irelu_model_number: str | None = None
    irelu_release_date: str | None = None
    irelu_features: list[IreluFeatureIn] = []


class ProductCreate(ProductUpdate):
    pass


class ProductResponse(ProductBase):
    id: int
    unit_price: float | None = None
    pocket_unit_price: float | None = None
    brand_id: int | None = None
    maker_id: int | None = None
    goods_category_name: str | None = None
    created_at: str
    updated_at: str
    images: list[ProductImageOut] = []
    features: list[FeatureTagOut] = []

    is_irelu: bool = False
    irelu_model_number: str | None = None
    irelu_release_date: str | None = None
    irelu_features: list[IreluFeatureOut] = []

    model_config = {"from_attributes": True}


class ProductListItem(BaseModel):
    id: int
    name: str
    category: str
    brand_name: str | None = None
    maker_name: str | None = None
    price: int | None = None
    jan_code: str | None = None
    thumbnail_url: str | None = None


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    total: int
