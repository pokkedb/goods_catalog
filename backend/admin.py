from sqladmin import ModelView
from wtforms import SelectField
from markupsafe import Markup

from models import (
    Brand,
    Maker,
    GoodsCategory,
    GoodsCategoryTarget,
    GoodsCategorySelflink,
    Product,
    ProductImage,
    ProductFeature,
    SleeveCover,
    BinderFile,
    Refill,
    Frame,
    OshiGoods,
    StorageView,
    DecoMaterialView,
    OtherView,
    IreluProduct,
    IreluFeature,
    IreluItem,
    IreluItemLink,
)

# schema.sql の CHECK制約と一致させた選択肢（自由入力によるDB制約違反を防ぐ）
PRODUCT_CATEGORY_CHOICES = [
    ("スリーブ＆カバー", "スリーブ＆カバー"), ("バインダー＆ファイル", "バインダー＆ファイル"),
    ("リフィル", "リフィル"), ("収納ケース", "収納ケース"), ("フレーム", "フレーム"),
    ("推し活グッズ", "推し活グッズ"), ("デコ素材", "デコ素材"), ("その他", "その他"),
]
SLEEVE_TYPE_CHOICES = [
    ("", "（未設定）"), ("ソフトタイプ", "ソフトタイプ"), ("ハードタイプ", "ハードタイプ"),
    ("PVC", "PVC"), ("硬質ケース", "硬質ケース"), ("その他", "その他"),
    ("テープ付き", "テープ付き"), ("超ハードタイプ", "超ハードタイプ"),
]
FILE_STANDARD_CHOICES = [
    ("", "（未設定）"), ("ポケット型ファイル", "ポケット型ファイル"), ("マガジン対応", "マガジン対応"),
    ("リング式バインダー", "リング式バインダー"), ("クリアファイル型", "クリアファイル型"),
]
OSHI_GOODS_SUBCATEGORY_CHOICES = [
    ("", "（未設定）"), ("アクスタケース", "アクスタケース"), ("うちわケース", "うちわケース"),
    ("トレカケース", "トレカケース"), ("ぬいぐるみ関連", "ぬいぐるみ関連"), ("ペンライトケース", "ペンライトケース"),
    ("推し活トート", "推し活トート"), ("推し活ポーチ", "推し活ポーチ"), ("推し活ファイル", "推し活ファイル"),
    ("その他", "その他"), ("缶バッジケース", "缶バッジケース"), ("カラビナ", "カラビナ"),
    ("推し活手帳", "推し活手帳"), ("痛バ", "痛バ"),
]
IRELU_CATEGORY_TYPE_CHOICES = [
    ("refill", "refill（リフィル）"), ("binder_file", "binder_file（バインダー＆ファイル）"),
    ("sleeve", "sleeve（スリーブ）"), ("other", "other（その他）"),
]
IRELU_MEDIA_TYPE_CHOICES = [
    ("", "（未設定）"), ("micosblog_リフィル", "micosblog_リフィル"), ("micosblog_スリーブ", "micosblog_スリーブ"),
    ("micosblog", "micosblog"), ("公式サイト", "公式サイト"), ("お知らせ", "お知らせ"),
]


def image_thumbnail(relative_url, size=60):
    """product_images.url（ローカル相対パス）からサムネイル<img>タグを組み立てる"""
    return Markup(
        f'<img src="/media/{relative_url}" loading="lazy" '
        f'style="max-height:{size}px;max-width:{size}px;object-fit:cover;'
        f'border-radius:4px;border:1px solid #ddd;">'
    )


class ProductAdmin(ModelView, model=Product):
    name = "商品"
    name_plural = "商品"
    icon = "fa-solid fa-box"
    category = "商品マスタ"

    column_list = [
        Product.id, Product.name, Product.category, Product.brand, Product.maker,
        Product.price, Product.jan_code,
    ]
    column_searchable_list = [Product.name, Product.jan_code, Product.notion_id]
    column_filters = [Product.category, Product.brand_id, Product.maker_id]
    column_sortable_list = [Product.id, Product.name, Product.category, Product.price]
    column_default_sort = [(Product.id, False)]

    column_details_exclude_list = [Product.notion_id]
    # 画像一覧をオブジェクト表記のリンクではなくサムネイル表示にする
    column_formatters_detail = {
        Product.images: lambda m, a: [image_thumbnail(img.url) for img in m.images],
    }
    # category は自由入力だとCHECK制約違反(SQLite側の分かりにくいエラー)になりうるためドロップダウン化
    form_overrides = {"category": SelectField}
    form_args = {"category": {"choices": PRODUCT_CATEGORY_CHOICES}}
    # unit_price / pocket_unit_price はSQLite側のGENERATED列（読み取り専用）のためフォームから除外
    form_excluded_columns = [
        Product.unit_price, Product.pocket_unit_price,
        Product.images, Product.features,
        Product.sleeve_cover, Product.binder_file, Product.refill, Product.frame, Product.oshi_goods,
        Product.irelu_product,
        Product.created_at, Product.updated_at,
    ]

    column_labels = {
        Product.id: "ID",
        Product.notion_id: "Notion ID",
        Product.name: "商品名",
        Product.category: "カテゴリ",
        Product.brand: "ブランド",
        Product.brand_id: "ブランドID",
        Product.maker: "発売元",
        Product.maker_id: "発売元ID",
        Product.jan_code: "JANコード",
        Product.price: "価格（円）",
        Product.quantity: "入枚数",
        Product.unit_price: "一枚単価（自動計算）",
        Product.pocket_count: "ポケット数",
        Product.pocket_unit_price: "ポケット単価（自動計算）",
        Product.outer_width_mm: "外寸横 (mm)",
        Product.outer_height_mm: "外寸縦 (mm)",
        Product.outer_depth_mm: "外寸奥行 (mm)",
        Product.outer_height2_mm: "外寸高さ (mm)",
        Product.spine_width_mm: "背幅 (mm)",
        Product.inner_width_mm: "内寸横 (mm)",
        Product.inner_height_mm: "内寸縦 (mm)",
        Product.inner_depth_mm: "内寸奥行 (mm)",
        Product.inner_height2_mm: "内寸高さ (mm)",
        Product.pocket_inner_width_mm: "ポケット内寸横 (mm)",
        Product.pocket_inner_height_mm: "ポケット内寸縦 (mm)",
        Product.thickness_mm: "厚さ (mm)",
        Product.weight_g: "重さ (g)",
        Product.free_description: "特徴自由記述",
        Product.concerns: "懸念点",
        Product.image_filename: "画像ファイル名",
        Product.blog_url: "ブログURL",
        Product.micosblog_notion_id: "micosblog参照ID",
        Product.my_block: "マイブロック",
        Product.shortcode: "ショートコード",
        Product.reference_url: "参考URL",
        Product.double_sided_check: "両面チェック",
        Product.generate_flag: "生成フラグ",
        Product.created_at: "作成日時",
        Product.updated_at: "更新日時",
        Product.images: "画像",
        Product.features: "特徴タグ",
        Product.sleeve_cover: "スリーブ＆カバー詳細",
        Product.binder_file: "バインダー＆ファイル詳細",
        Product.refill: "リフィル詳細",
        Product.frame: "フレーム詳細",
        Product.oshi_goods: "推し活グッズ詳細",
        Product.irelu_product: "irelu連携",
    }


class ProductImageAdmin(ModelView, model=ProductImage):
    name = "商品画像"
    name_plural = "商品画像"
    icon = "fa-solid fa-image"
    category = "商品マスタ"

    column_list = [ProductImage.id, ProductImage.product, ProductImage.url, ProductImage.sort_order]
    column_searchable_list = [ProductImage.url]
    form_excluded_columns = [ProductImage.source_url]

    column_formatters = {
        ProductImage.url: lambda m, a: Markup(f'{image_thumbnail(m.url, size=40)} {m.url}'),
    }
    column_formatters_detail = {
        ProductImage.url: lambda m, a: Markup(f'{image_thumbnail(m.url, size=200)}<br>{m.url}'),
    }

    column_labels = {
        ProductImage.id: "ID",
        ProductImage.product: "商品",
        ProductImage.source_url: "元URL（Notion/Dropbox）",
        ProductImage.url: "表示URL（ローカルパス）",
        ProductImage.sort_order: "並び順",
    }


class ProductFeatureAdmin(ModelView, model=ProductFeature):
    name = "特徴タグ"
    name_plural = "特徴タグ"
    icon = "fa-solid fa-tags"
    category = "商品マスタ"

    column_list = [ProductFeature.id, ProductFeature.product, ProductFeature.group_no, ProductFeature.tag]
    column_filters = [ProductFeature.group_no]
    column_searchable_list = [ProductFeature.tag]

    column_labels = {
        ProductFeature.id: "ID",
        ProductFeature.product: "商品",
        ProductFeature.group_no: "グループ (1:見た目 2:実用性 3:利用シーン 4:素材 5:カラー 6:購入対象者)",
        ProductFeature.tag: "タグ",
    }


class BrandAdmin(ModelView, model=Brand):
    name = "ブランド"
    name_plural = "ブランド"
    icon = "fa-solid fa-tag"
    category = "マスタ"

    column_list = [Brand.id, Brand.name]
    column_searchable_list = [Brand.name]
    form_excluded_columns = [Brand.products]

    column_labels = {
        Brand.id: "ID",
        Brand.notion_id: "Notion ID",
        Brand.name: "ブランド名",
        Brand.products: "商品",
    }


class MakerAdmin(ModelView, model=Maker):
    name = "発売元"
    name_plural = "発売元"
    icon = "fa-solid fa-industry"
    category = "マスタ"

    column_list = [Maker.id, Maker.name]
    column_searchable_list = [Maker.name]
    form_excluded_columns = [Maker.products]

    column_labels = {
        Maker.id: "ID",
        Maker.notion_id: "Notion ID",
        Maker.name: "発売元名",
        Maker.products: "商品",
    }


class GoodsCategoryAdmin(ModelView, model=GoodsCategory):
    name = "グッズカテゴリ"
    name_plural = "グッズカテゴリ"
    icon = "fa-solid fa-ruler"
    category = "マスタ"

    column_list = [
        GoodsCategory.id, GoodsCategory.name,
        GoodsCategory.width_mm, GoodsCategory.height_mm, GoodsCategory.depth_mm,
    ]
    column_searchable_list = [GoodsCategory.name]
    form_excluded_columns = [GoodsCategory.goods_size_label, GoodsCategory.targets]

    column_labels = {
        GoodsCategory.id: "ID",
        GoodsCategory.notion_id: "Notion ID",
        GoodsCategory.name: "グッズカテゴリ名",
        GoodsCategory.width_mm: "横幅 (mm)",
        GoodsCategory.height_mm: "縦幅 (mm)",
        GoodsCategory.depth_mm: "幅（厚み） (mm) ※Blu-ray等ディスクケース類のみ使用",
        GoodsCategory.goods_size_label: "グッズサイズ表示（自動生成）",
        GoodsCategory.targets: "対象商品",
    }


class GoodsCategoryTargetAdmin(ModelView, model=GoodsCategoryTarget):
    name = "グッズカテゴリ対象商品"
    name_plural = "グッズカテゴリ対象商品"
    icon = "fa-solid fa-list"
    category = "マスタ"

    column_list = [GoodsCategoryTarget.goods_category, GoodsCategoryTarget.target_item]

    column_labels = {
        GoodsCategoryTarget.goods_category: "グッズカテゴリ",
        GoodsCategoryTarget.target_item: "対象商品",
    }


class SleeveCoverAdmin(ModelView, model=SleeveCover):
    name = "スリーブ＆カバー"
    name_plural = "スリーブ＆カバー"
    icon = "fa-solid fa-layer-group"
    category = "カテゴリ別詳細"

    column_list = [SleeveCover.product, SleeveCover.sleeve_type, SleeveCover.goods_category]

    form_overrides = {"sleeve_type": SelectField}
    form_args = {"sleeve_type": {"choices": SLEEVE_TYPE_CHOICES}}

    column_labels = {
        SleeveCover.product: "商品",
        SleeveCover.sleeve_type: "スリーブタイプ",
        SleeveCover.goods_category: "対象グッズカテゴリ",
    }


class BinderFileAdmin(ModelView, model=BinderFile):
    name = "バインダー＆ファイル"
    name_plural = "バインダー＆ファイル"
    icon = "fa-solid fa-book"
    category = "カテゴリ別詳細"

    column_list = [BinderFile.product, BinderFile.file_standard]

    form_overrides = {"file_standard": SelectField}
    form_args = {"file_standard": {"choices": FILE_STANDARD_CHOICES}}

    column_labels = {
        BinderFile.product: "商品",
        BinderFile.file_standard: "ファイル規格",
    }


class RefillAdmin(ModelView, model=Refill):
    name = "リフィル"
    name_plural = "リフィル"
    icon = "fa-solid fa-file-lines"
    category = "カテゴリ別詳細"

    column_list = [Refill.product, Refill.pocket_count_label, Refill.refill_standard]

    column_labels = {
        Refill.product: "商品",
        Refill.pocket_count_label: "リフィルポケット数",
        Refill.refill_standard: "リフィル規格",
    }


class FrameAdmin(ModelView, model=Frame):
    name = "フレーム"
    name_plural = "フレーム"
    icon = "fa-solid fa-image-portrait"
    category = "カテゴリ別詳細"

    column_list = [Frame.product, Frame.has_stand, Frame.has_wall_hook]

    column_labels = {
        Frame.product: "商品",
        Frame.has_stand: "スタンド (1:あり 0:なし)",
        Frame.has_wall_hook: "壁掛けフック (1:あり 0:なし)",
    }


class OshiGoodsAdmin(ModelView, model=OshiGoods):
    name = "推し活グッズ"
    name_plural = "推し活グッズ"
    icon = "fa-solid fa-star"
    category = "カテゴリ別詳細"

    column_list = [OshiGoods.product, OshiGoods.subcategory, OshiGoods.capacity_estimate]
    column_filters = [OshiGoods.subcategory]

    form_overrides = {"subcategory": SelectField}
    form_args = {"subcategory": {"choices": OSHI_GOODS_SUBCATEGORY_CHOICES}}

    column_labels = {
        OshiGoods.product: "商品",
        OshiGoods.subcategory: "推し活グッズカテゴリ",
        OshiGoods.has_hanging_hardware: "吊り下げ金具 (1:あり 0:なし)",
        OshiGoods.has_charm_hole: "チャーム用穴 (1:あり 0:なし)",
        OshiGoods.capacity_estimate: "収納可能目安",
    }


# 収納ケース／デコ素材／その他 の3カテゴリは固有列を持たずproducts.categoryのみで判別する設計
# （Phase 0調査で確定）。専用テーブルがないため、schema.sql側で用意済みのロールアップ再現VIEW
# （storages_view等）を読み取り専用でそのまま閲覧に使う。8カテゴリ全てをサイドバーに揃えるため。
class StorageViewAdmin(ModelView, model=StorageView):
    name = "収納ケース"
    name_plural = "収納ケース"
    icon = "fa-solid fa-box-archive"
    category = "カテゴリ別詳細"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        StorageView.id, StorageView.name, StorageView.price,
        StorageView.outer_width_mm, StorageView.outer_height_mm, StorageView.outer_depth_mm,
    ]
    column_searchable_list = [StorageView.name]

    column_labels = {
        StorageView.id: "商品ID",
        StorageView.notion_id: "Notion ID",
        StorageView.name: "商品名",
        StorageView.price: "価格（円）",
        StorageView.outer_width_mm: "外寸横 (mm)",
        StorageView.outer_height_mm: "外寸縦 (mm)",
        StorageView.outer_depth_mm: "外寸奥行 (mm)",
        StorageView.inner_width_mm: "内寸横 (mm)",
        StorageView.inner_height_mm: "内寸縦 (mm)",
        StorageView.inner_depth_mm: "内寸奥行 (mm)",
        StorageView.created_at: "作成日時",
        StorageView.maker_name: "発売元",
    }


class DecoMaterialViewAdmin(ModelView, model=DecoMaterialView):
    name = "デコ素材"
    name_plural = "デコ素材"
    icon = "fa-solid fa-gem"
    category = "カテゴリ別詳細"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [
        DecoMaterialView.id, DecoMaterialView.name, DecoMaterialView.price,
        DecoMaterialView.brand_name, DecoMaterialView.maker_name,
    ]
    column_searchable_list = [DecoMaterialView.name]

    column_labels = {
        DecoMaterialView.id: "商品ID",
        DecoMaterialView.notion_id: "Notion ID",
        DecoMaterialView.name: "商品名",
        DecoMaterialView.jan_code: "JANコード",
        DecoMaterialView.price: "価格（円）",
        DecoMaterialView.quantity: "入枚数",
        DecoMaterialView.outer_width_mm: "外寸横 (mm)",
        DecoMaterialView.outer_height_mm: "外寸縦 (mm)",
        DecoMaterialView.created_at: "作成日時",
        DecoMaterialView.brand_name: "ブランド",
        DecoMaterialView.maker_name: "発売元",
    }


class OtherViewAdmin(ModelView, model=OtherView):
    name = "その他"
    name_plural = "その他"
    icon = "fa-solid fa-ellipsis"
    category = "カテゴリ別詳細"

    can_create = False
    can_edit = False
    can_delete = False

    column_list = [OtherView.id, OtherView.name, OtherView.price, OtherView.maker_name]
    column_searchable_list = [OtherView.name]

    column_labels = {
        OtherView.id: "商品ID",
        OtherView.notion_id: "Notion ID",
        OtherView.name: "商品名",
        OtherView.jan_code: "JANコード",
        OtherView.price: "価格（円）",
        OtherView.outer_width_mm: "外寸横 (mm)",
        OtherView.outer_height_mm: "外寸縦 (mm)",
        OtherView.created_at: "作成日時",
        OtherView.maker_name: "発売元",
    }


class IreluProductAdmin(ModelView, model=IreluProduct):
    name = "ireluリンク商品"
    name_plural = "ireluリンク商品"
    icon = "fa-solid fa-link"
    category = "irelu"

    column_list = [
        IreluProduct.id, IreluProduct.product, IreluProduct.category_type,
        IreluProduct.model_number, IreluProduct.release_date,
    ]
    column_filters = [IreluProduct.category_type]

    form_overrides = {"category_type": SelectField}
    form_args = {"category_type": {"choices": IRELU_CATEGORY_TYPE_CHOICES}}

    column_labels = {
        IreluProduct.id: "ID",
        IreluProduct.notion_id: "Notion ID",
        IreluProduct.product: "商品",
        IreluProduct.category_type: "カテゴリ種別",
        IreluProduct.model_number: "品番",
        IreluProduct.release_date: "発売日",
        IreluProduct.generate_flag: "生成フラグ",
        IreluProduct.features: "irelu特徴",
        IreluProduct.item_links: "irelu ITEM紐付け",
    }


class IreluFeatureAdmin(ModelView, model=IreluFeature):
    name = "irelu特徴"
    name_plural = "irelu特徴"
    icon = "fa-solid fa-list-check"
    category = "irelu"

    column_list = [
        IreluFeature.id, IreluFeature.irelu_product, IreluFeature.feature_no,
        IreluFeature.title,
    ]

    column_labels = {
        IreluFeature.id: "ID",
        IreluFeature.irelu_product: "ireluリンク商品",
        IreluFeature.feature_no: "特徴番号 (1〜5)",
        IreluFeature.title: "特徴タイトル",
        IreluFeature.description: "特徴概要",
    }


class IreluItemAdmin(ModelView, model=IreluItem):
    name = "irelu ITEM"
    name_plural = "irelu ITEM"
    icon = "fa-solid fa-newspaper"
    category = "irelu"

    column_list = [IreluItem.id, IreluItem.name, IreluItem.media_type]

    form_overrides = {"media_type": SelectField}
    form_args = {"media_type": {"choices": IRELU_MEDIA_TYPE_CHOICES}}

    column_labels = {
        IreluItem.id: "ID",
        IreluItem.notion_id: "Notion ID",
        IreluItem.name: "名前",
        IreluItem.media_type: "媒体",
        IreluItem.generate_flag: "生成フラグ",
        IreluItem.item_links: "紐付くirelu商品",
    }


class IreluItemLinkAdmin(ModelView, model=IreluItemLink):
    name = "irelu ITEM 紐付け"
    name_plural = "irelu ITEM 紐付け"
    icon = "fa-solid fa-diagram-project"
    category = "irelu"

    column_list = [IreluItemLink.irelu_item, IreluItemLink.irelu_product]

    column_labels = {
        IreluItemLink.irelu_item: "irelu ITEM",
        IreluItemLink.irelu_product: "ireluリンク商品",
    }


ALL_ADMIN_VIEWS = [
    ProductAdmin,
    ProductImageAdmin,
    ProductFeatureAdmin,
    BrandAdmin,
    MakerAdmin,
    GoodsCategoryAdmin,
    GoodsCategoryTargetAdmin,
    SleeveCoverAdmin,
    BinderFileAdmin,
    RefillAdmin,
    FrameAdmin,
    OshiGoodsAdmin,
    StorageViewAdmin,
    DecoMaterialViewAdmin,
    OtherViewAdmin,
    IreluProductAdmin,
    IreluFeatureAdmin,
    IreluItemAdmin,
    IreluItemLinkAdmin,
]
