# migration/etl/transform.py
"""
Phase 1 ETL: Notionの生ページJSON -> SQLite投入用dictへの変換ロジック。

このモジュールはDBアクセスを一切行わない純粋関数群。
relation先の実体（ブランド名など）は解決せず、`*_notion_id` というキー名で
関連先のNotion page_idをそのまま持たせる。実際のinteger FKへの解決は
load.py が notion_id -> id のマップを使って行う。

カテゴリ判定・列対応は SPEC.md「全プロパティ対応表」と一致させている。
"""

CATEGORY_RELATION_PROPS = [
    "スリーブ＆カバー", "バインダー＆ファイル", "リフィル",
    "収納ケース", "フレーム", "推し活グッズ", "デコ素材", "その他",
]

# irelu_products.category_type の値との対応
IRELU_SOURCE_TO_CATEGORY_TYPE = {
    "irelu_refill_db": "refill",
    "irelu_binder_file_db": "binder_file",
    "irelu_sleeve_db": "sleeve",
    "irelu_other_db": "other",
}

# irelu_item_db の4関連先プロパティ -> irelu_productsソースDBキー
IRELU_ITEM_LINK_PROPS = {
    "ireluリフィル": "irelu_refill_db",
    "ireluバインダーファイル": "irelu_binder_file_db",
    "ireluスリーブ": "irelu_sleeve_db",
    "ireluその他": "irelu_other_db",
}


# ------------------------------------------------------------
# 汎用プロパティ抽出（Notion RAW JSON -> Pythonの素朴な値）
# ------------------------------------------------------------

def get_prop(page, name):
    return page["properties"].get(name)


def get_title(page):
    for prop in page["properties"].values():
        if prop["type"] == "title":
            arr = prop["title"]
            return arr[0]["plain_text"] if arr else None
    return None


def extract_number(prop):
    if prop is None or prop["type"] != "number":
        return None
    return prop["number"]


def extract_rich_text(prop):
    if prop is None or prop["type"] != "rich_text":
        return None
    arr = prop["rich_text"]
    return arr[0]["plain_text"] if arr else None


def extract_text_like(prop):
    """rich_text/select/multi_selectのいずれでも文字列として取り出す（irelu_特徴N概要のプロパティ型ゆれ対応）"""
    if prop is None:
        return None
    t = prop["type"]
    if t == "rich_text":
        arr = prop["rich_text"]
        return arr[0]["plain_text"] if arr else None
    if t == "select":
        return prop["select"]["name"] if prop["select"] else None
    if t == "multi_select":
        names = [i["name"] for i in prop["multi_select"]]
        return "、".join(names) if names else None
    return None


def extract_select(prop):
    if prop is None or prop["type"] != "select":
        return None
    return prop["select"]["name"] if prop["select"] else None


def extract_multi_select(prop):
    if prop is None or prop["type"] != "multi_select":
        return []
    return [i["name"] for i in prop["multi_select"]]


def extract_checkbox(prop, default=0):
    if prop is None or prop["type"] != "checkbox":
        return default
    return 1 if prop["checkbox"] else 0


def extract_url(prop):
    if prop is None or prop["type"] != "url":
        return None
    return prop["url"]


def extract_date(prop):
    if prop is None or prop["type"] != "date":
        return None
    d = prop["date"]
    return d["start"] if d else None


def extract_created_time(prop):
    if prop is None or prop["type"] != "created_time":
        return None
    return prop["created_time"]


def extract_relation_ids(prop):
    if prop is None or prop["type"] != "relation":
        return []
    return [r["id"] for r in prop["relation"]]


def extract_relation_id_first(prop):
    ids = extract_relation_ids(prop)
    return ids[0] if ids else None


def extract_rollup_url(prop):
    """ブログURL用: rollup(array of url)の最初の非nullを返す"""
    if prop is None or prop["type"] != "rollup":
        return None
    rollup = prop["rollup"]
    if rollup.get("type") != "array":
        return None
    for item in rollup["array"]:
        if item.get("type") == "url" and item.get("url"):
            return item["url"]
    return None


def extract_files_urls(prop):
    """files プロパティから (url, source_type) のリストを返す。source_type は 'external' か 'file'"""
    if prop is None or prop["type"] != "files":
        return []
    result = []
    for f in prop["files"]:
        if f["type"] == "external":
            result.append((f["external"]["url"], "external"))
        elif f["type"] == "file":
            result.append((f["file"]["url"], "file"))
    return result


def extract_ho_flag(prop):
    """「あり」「なし」select を 1/0/None に変換（スタンド・壁掛けフック・吊り下げ金具・チャーム用穴用）"""
    value = extract_select(prop)
    if value is None:
        return None
    if value == "あり":
        return 1
    if value == "なし":
        return 0
    return None


# ------------------------------------------------------------
# brands / makers
# ------------------------------------------------------------

def transform_brand(page):
    return {"notion_id": page["id"], "name": get_title(page)}


def transform_maker(page):
    return {"notion_id": page["id"], "name": get_title(page)}


# ------------------------------------------------------------
# goods_categories
# ------------------------------------------------------------

def transform_goods_category(page):
    return {
        "notion_id": page["id"],
        "name": get_title(page),
        "width_mm": extract_number(get_prop(page, "横幅")),
        "height_mm": extract_number(get_prop(page, "縦幅")),
        "depth_mm": extract_number(get_prop(page, "幅")),
    }


def transform_goods_category_targets(page):
    items = extract_multi_select(get_prop(page, "対象商品"))
    return [
        {"goods_category_notion_id": page["id"], "target_item": item}
        for item in items
    ]


def transform_goods_category_selflinks(page):
    linked_ids = extract_relation_ids(get_prop(page, "selflink"))
    return [
        {
            "goods_category_notion_id": page["id"],
            "linked_goods_category_notion_id": linked_id,
        }
        for linked_id in linked_ids
    ]


# ------------------------------------------------------------
# products (商品DB)
# ------------------------------------------------------------

def determine_category(page):
    """8つのカテゴリrelationプロパティのうち最初に非空のものをカテゴリ名として返す。
    どれも空なら None（Phase 0調査で判明した11件のカテゴリ未設定商品に該当）。
    """
    for cat in CATEGORY_RELATION_PROPS:
        ids = extract_relation_ids(get_prop(page, cat))
        if ids:
            return cat
    return None


def transform_product(page):
    category = determine_category(page)

    return {
        "notion_id": page["id"],
        "name": get_title(page),
        "category": category,
        "brand_notion_id": extract_relation_id_first(get_prop(page, "ブランド")),
        "maker_notion_id": extract_relation_id_first(get_prop(page, "発売元")),
        "jan_code": extract_rich_text(get_prop(page, "JANコード")),
        "price": extract_number(get_prop(page, "価格")),
        "quantity": extract_number(get_prop(page, "入枚数")),
        "pocket_count": extract_number(get_prop(page, "ポケット数")),
        "outer_width_mm": extract_number(get_prop(page, "外寸横")),
        "outer_height_mm": extract_number(get_prop(page, "外寸縦")),
        "outer_depth_mm": extract_number(get_prop(page, "外寸奥行")),
        "outer_height2_mm": extract_number(get_prop(page, "外寸高さ")),
        "spine_width_mm": extract_number(get_prop(page, "背幅")),
        "inner_width_mm": extract_number(get_prop(page, "内寸横")),
        "inner_height_mm": extract_number(get_prop(page, "内寸縦")),
        "inner_depth_mm": extract_number(get_prop(page, "内寸奥行")),
        "inner_height2_mm": extract_number(get_prop(page, "内寸高さ")),
        "pocket_inner_width_mm": extract_number(get_prop(page, "ポケット内寸横")),
        "pocket_inner_height_mm": extract_number(get_prop(page, "ポケット内寸縦")),
        "thickness_mm": extract_number(get_prop(page, "厚さ")),
        "weight_g": extract_number(get_prop(page, "重さ")),
        "free_description": extract_rich_text(get_prop(page, "特徴自由記述")),
        "concerns": extract_rich_text(get_prop(page, "懸念点")),
        "image_filename": extract_rich_text(get_prop(page, "画像ファイル名")),
        "blog_url": extract_rollup_url(get_prop(page, "ブログURL")),
        "micosblog_notion_id": extract_relation_id_first(get_prop(page, "micosblog")),
        "my_block": extract_rich_text(get_prop(page, "マイブロック")),
        "shortcode": extract_rich_text(get_prop(page, "ショートコード")),
        "reference_url": extract_url(get_prop(page, "参考URL")),
        "double_sided_check": extract_checkbox(get_prop(page, "両面チェック")),
        "generate_flag": extract_checkbox(get_prop(page, "生成")),
        "created_at": extract_created_time(get_prop(page, "作成日時")),
    }


PRODUCT_FEATURE_GROUPS = [
    (1, "特徴1_見た目"),
    (2, "特徴2_実用性"),
    (3, "特徴3_利用シーン"),
    (4, "特徴4_素材"),
    (5, "特徴5_カラー"),
    (6, "特徴6_購入対象者"),
]


def transform_product_features(page):
    rows = []
    for group_no, prop_name in PRODUCT_FEATURE_GROUPS:
        for tag in extract_multi_select(get_prop(page, prop_name)):
            rows.append({
                "product_notion_id": page["id"],
                "group_no": group_no,
                "tag": tag,
            })
    return rows


# ------------------------------------------------------------
# カテゴリ別8DB: product_images + サブタイプテーブル
# ------------------------------------------------------------

def transform_category_images(page):
    """カテゴリ別DBの「画像」プロパティ -> product_images行（product_notion_id付き）"""
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return []
    urls = extract_files_urls(get_prop(page, "画像"))
    return [
        {
            "product_notion_id": product_notion_id,
            "url": url,
            "source_type": source_type,
            "sort_order": i,
        }
        for i, (url, source_type) in enumerate(urls)
    ]


def transform_sleeve_cover(page):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "product_notion_id": product_notion_id,
        "sleeve_type": extract_select(get_prop(page, "スリーブタイプ")),
        "goods_category_notion_id": extract_relation_id_first(get_prop(page, "グッズカテゴリ")),
    }


def transform_binder_file(page):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "product_notion_id": product_notion_id,
        "file_standard": extract_select(get_prop(page, "ファイル規格")),
    }


def transform_refill(page):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "product_notion_id": product_notion_id,
        "pocket_count_label": extract_select(get_prop(page, "リフィルポケット数")),
        "refill_standard": extract_select(get_prop(page, "リフィル規格")),
    }


def transform_frame(page):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "product_notion_id": product_notion_id,
        "has_stand": extract_ho_flag(get_prop(page, "スタンド")),
        "has_wall_hook": extract_ho_flag(get_prop(page, "壁掛けフック")),
    }


def transform_oshi_goods(page):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "product_notion_id": product_notion_id,
        "subcategory": extract_select(get_prop(page, "推し活グッズカテゴリ")),
        "has_hanging_hardware": extract_ho_flag(get_prop(page, "吊り下げ金具")),
        "has_charm_hole": extract_ho_flag(get_prop(page, "チャーム用穴")),
        "capacity_estimate": extract_number(get_prop(page, "収納可能目安")),
    }


# ------------------------------------------------------------
# irelu関連
# ------------------------------------------------------------

def transform_irelu_product(page, source_key):
    product_notion_id = extract_relation_id_first(get_prop(page, "商品DB"))
    if not product_notion_id:
        return None
    return {
        "notion_id": page["id"],
        "product_notion_id": product_notion_id,
        "category_type": IRELU_SOURCE_TO_CATEGORY_TYPE[source_key],
        "model_number": extract_rich_text(get_prop(page, "品番")),
        "release_date": extract_date(get_prop(page, "発売日")),
        "generate_flag": extract_checkbox(get_prop(page, "生成")),
    }


IRELU_FEATURE_GROUPS = [1, 2, 3, 4, 5]


def transform_irelu_features(page):
    rows = []
    for n in IRELU_FEATURE_GROUPS:
        title = extract_rich_text(get_prop(page, f"irelu_特徴{n}"))
        description = extract_text_like(get_prop(page, f"irelu_特徴{n}概要"))
        if title is None and description is None:
            continue
        rows.append({
            "irelu_product_notion_id": page["id"],
            "feature_no": n,
            "title": title,
            "description": description,
        })
    return rows


def transform_irelu_item(page):
    return {
        "notion_id": page["id"],
        "name": get_title(page),
        "media_type": extract_select(get_prop(page, "媒体")),
        "generate_flag": extract_checkbox(get_prop(page, "生成")),
    }


def transform_irelu_item_links(page):
    rows = []
    for prop_name in IRELU_ITEM_LINK_PROPS:
        for irelu_product_notion_id in extract_relation_ids(get_prop(page, prop_name)):
            rows.append({
                "irelu_item_notion_id": page["id"],
                "irelu_product_notion_id": irelu_product_notion_id,
            })
    return rows
