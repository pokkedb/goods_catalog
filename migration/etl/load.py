# migration/etl/load.py
"""
Phase 1 ETL: migration/etl/raw_dump/*.json を読み込み、transform.pyで変換した上で
SQLite（/pokke/databases/goods_catalog/goods_catalog.db）へ notion_id をキーに
冪等（再実行しても重複しない）にupsertする。

事前に fetch.py と create_schema.py を実行しておくこと。

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/load.py
"""
import json
import sqlite3
from pathlib import Path

import transform as tf

RAW_DIR = Path(__file__).resolve().parent / "raw_dump"
DB_PATH = Path("/pokke/databases/goods_catalog/goods_catalog.db")
REPORT_PATH = Path(__file__).resolve().parent / "load_report.md"

CATEGORY_DB_KEYS = [
    "sleeve_cover_db", "binder_file_db", "refill_db", "storage_db",
    "frame_db", "oshi_goods_db", "deco_material_db", "other_db",
]

# カテゴリ別DBキー -> サブタイプ変換関数（storage/deco_material/otherは固有列を持たないためNone）
CATEGORY_SUBTYPE_TRANSFORM = {
    "sleeve_cover_db": ("sleeve_covers", tf.transform_sleeve_cover),
    "binder_file_db": ("binder_files", tf.transform_binder_file),
    "refill_db": ("refills", tf.transform_refill),
    "storage_db": None,
    "frame_db": ("frames", tf.transform_frame),
    "oshi_goods_db": ("oshi_goods", tf.transform_oshi_goods),
    "deco_material_db": None,
    "other_db": None,
}

IRELU_PRODUCT_DB_KEYS = [
    "irelu_refill_db", "irelu_binder_file_db", "irelu_sleeve_db", "irelu_other_db",
]


def load_json(key):
    path = RAW_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} が見つかりません。先に fetch.py を実行してください。")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def upsert(conn, table, key_col, row, id_col="id"):
    """key_col（notion_id等）をキーに1行upsertし、id_col の値を返す"""
    cols = list(row.keys())
    cur = conn.execute(f"SELECT {id_col} FROM {table} WHERE {key_col} = ?", (row[key_col],))
    existing = cur.fetchone()
    if existing:
        set_cols = [c for c in cols if c != key_col]
        if set_cols:
            set_clause = ", ".join(f"{c} = ?" for c in set_cols)
            values = [row[c] for c in set_cols] + [row[key_col]]
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE {key_col} = ?", values)
        return existing[0]

    col_list = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    conn.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", [row[c] for c in cols])
    return conn.execute(f"SELECT {id_col} FROM {table} WHERE {key_col} = ?", (row[key_col],)).fetchone()[0]


def replace_children(conn, table, parent_col, parent_id, rows):
    """子テーブルを parent_id に紐づく分だけ削除してから再挿入する（冪等な多値展開）"""
    conn.execute(f"DELETE FROM {table} WHERE {parent_col} = ?", (parent_id,))
    for row in rows:
        cols = list(row.keys())
        col_list = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", [row[c] for c in cols])


def sync_product_images(conn, product_id, rows):
    """product_images を source_url をキーに差分同期する。

    replace_children（削除→全再挿入）を使うと、download_images.py がurlをローカルパスに
    書き換えた既存行まで消えてしまい、load.py を再実行するたびに全画像の再ダウンロードが
    必要になってしまう。そのため source_url が一致する既存行は url を触らずに残し、
    Notion側で増えた画像だけ新規挿入、消えた画像だけ削除する。

    rows: [{"source_url": ..., "sort_order": ...}, ...]

    注意: backend/routers/products.py の画像アップロード機能で追加された画像は
    source_urlが"upload:"始まりでNotion側のデータには存在しないため、削除対象の
    判定はsource_urlがhttp(s)始まり（Notion/Dropbox由来）の行だけに限定する。
    そうしないとユーザーがアップロードした画像がNotion再同期のたびに消えてしまう。
    """
    # 同じsource_urlが同一呼び出し内で複数回渡された場合に備えて重複除去する
    # （カテゴリ別DB側に同一画像を持つ重複レコードが残っている等のケースへの防御）
    deduped_rows = list({r["source_url"]: r for r in rows}.values())

    existing = conn.execute(
        "SELECT id, source_url FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchall()
    existing_by_source = {source_url: image_id for image_id, source_url in existing}
    target_source_urls = {r["source_url"] for r in deduped_rows}

    for source_url, image_id in existing_by_source.items():
        is_notion_managed = source_url.startswith("http://") or source_url.startswith("https://")
        if is_notion_managed and source_url not in target_source_urls:
            conn.execute("DELETE FROM product_images WHERE id = ?", (image_id,))

    for r in deduped_rows:
        if r["source_url"] in existing_by_source:
            conn.execute(
                "UPDATE product_images SET sort_order = ? WHERE id = ?",
                (r["sort_order"], existing_by_source[r["source_url"]]),
            )
        else:
            conn.execute(
                "INSERT INTO product_images (product_id, source_url, url, sort_order) VALUES (?, ?, ?, ?)",
                (product_id, r["source_url"], r["source_url"], r["sort_order"]),
            )


def main():
    warnings = []

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
    ).fetchone()
    if not exists:
        conn.close()
        raise RuntimeError(
            f"{DB_PATH} にテーブルがありません。先に create_schema.py を実行してください。"
        )

    # --- 1. brands / makers ---
    brand_id_map = {}
    for page in load_json("brand_db"):
        row = tf.transform_brand(page)
        brand_id_map[row["notion_id"]] = upsert(conn, "brands", "notion_id", row)
    print(f"brands: {len(brand_id_map)}件")

    maker_id_map = {}
    for page in load_json("maker_db"):
        row = tf.transform_maker(page)
        maker_id_map[row["notion_id"]] = upsert(conn, "makers", "notion_id", row)
    print(f"makers: {len(maker_id_map)}件")

    # --- 2. goods_categories (+targets, +selflinks) ---
    goods_category_pages = load_json("goods_category_db")
    goods_category_id_map = {}
    for page in goods_category_pages:
        row = tf.transform_goods_category(page)
        goods_category_id_map[row["notion_id"]] = upsert(conn, "goods_categories", "notion_id", row)
    print(f"goods_categories: {len(goods_category_id_map)}件")

    for page in goods_category_pages:
        gc_id = goods_category_id_map[page["id"]]
        target_rows = [
            {"goods_category_id": gc_id, "target_item": r["target_item"]}
            for r in tf.transform_goods_category_targets(page)
        ]
        replace_children(conn, "goods_category_targets", "goods_category_id", gc_id, target_rows)

        selflink_rows = []
        for r in tf.transform_goods_category_selflinks(page):
            linked_id = goods_category_id_map.get(r["linked_goods_category_notion_id"])
            if linked_id is None:
                warnings.append(f"selflink参照切れ: {page['id']} -> {r['linked_goods_category_notion_id']}")
                continue
            selflink_rows.append({"goods_category_id": gc_id, "linked_goods_category_id": linked_id})
        replace_children(conn, "goods_category_selflinks", "goods_category_id", gc_id, selflink_rows)

    # --- 3. products (+features) ---
    product_pages = load_json("product_db")
    product_id_map = {}
    skipped_no_category = []
    for page in product_pages:
        row = tf.transform_product(page)
        if row["category"] is None:
            skipped_no_category.append({"notion_id": row["notion_id"], "name": row["name"]})
            continue

        row["brand_id"] = brand_id_map.get(row.pop("brand_notion_id"))
        row["maker_id"] = maker_id_map.get(row.pop("maker_notion_id"))
        product_id_map[row["notion_id"]] = upsert(conn, "products", "notion_id", row)
    print(f"products: {len(product_id_map)}件（カテゴリ未設定でスキップ: {len(skipped_no_category)}件）")

    for page in product_pages:
        if page["id"] not in product_id_map:
            continue
        product_id = product_id_map[page["id"]]
        feature_rows = [
            {"product_id": product_id, "group_no": r["group_no"], "tag": r["tag"]}
            for r in tf.transform_product_features(page)
        ]
        replace_children(conn, "product_features", "product_id", product_id, feature_rows)

    # --- 4. カテゴリ別8DB: product_images + サブタイプテーブル ---
    image_rows_by_product = {}
    for db_key in CATEGORY_DB_KEYS:
        pages = load_json(db_key)
        for page in pages:
            for img in tf.transform_category_images(page):
                product_id = product_id_map.get(img["product_notion_id"])
                if product_id is None:
                    warnings.append(f"{db_key}: 画像の紐付け先product未検出 ({img['product_notion_id']})")
                    continue
                image_rows_by_product.setdefault(product_id, []).append(
                    {"source_url": img["url"], "sort_order": img["sort_order"]}
                )

            subtype = CATEGORY_SUBTYPE_TRANSFORM.get(db_key)
            if subtype is None:
                continue
            table_name, transform_fn = subtype
            sub_row = transform_fn(page)
            if sub_row is None:
                continue
            product_id = product_id_map.get(sub_row.pop("product_notion_id"))
            if product_id is None:
                warnings.append(f"{db_key}: サブタイプ行の紐付け先product未検出")
                continue
            if "goods_category_notion_id" in sub_row:
                sub_row["goods_category_id"] = goods_category_id_map.get(
                    sub_row.pop("goods_category_notion_id")
                )
            sub_row["product_id"] = product_id
            upsert(conn, table_name, "product_id", sub_row, id_col="product_id")

    image_count = 0
    for product_id, rows in image_rows_by_product.items():
        sync_product_images(conn, product_id, rows)
        image_count += len(rows)
    print(f"product_images: {image_count}件（{len(image_rows_by_product)}商品分）")

    # --- 5. irelu関連 ---
    irelu_product_id_map = {}
    for db_key in IRELU_PRODUCT_DB_KEYS:
        for page in load_json(db_key):
            row = tf.transform_irelu_product(page, db_key)
            if row is None:
                warnings.append(f"{db_key}: 商品DB未紐付けのためirelu_products登録スキップ ({page['id']})")
                continue
            product_id = product_id_map.get(row.pop("product_notion_id"))
            if product_id is None:
                warnings.append(f"{db_key}: irelu_productsの紐付け先product未検出 ({page['id']})")
                continue
            row["product_id"] = product_id
            irelu_product_id_map[row["notion_id"]] = upsert(conn, "irelu_products", "notion_id", row)
    print(f"irelu_products: {len(irelu_product_id_map)}件")

    for db_key in IRELU_PRODUCT_DB_KEYS:
        for page in load_json(db_key):
            if page["id"] not in irelu_product_id_map:
                continue
            irelu_product_id = irelu_product_id_map[page["id"]]
            feature_rows = [
                {
                    "irelu_product_id": irelu_product_id,
                    "feature_no": r["feature_no"],
                    "title": r["title"],
                    "description": r["description"],
                }
                for r in tf.transform_irelu_features(page)
            ]
            replace_children(conn, "irelu_features", "irelu_product_id", irelu_product_id, feature_rows)

    irelu_item_pages = load_json("irelu_item_db")
    irelu_item_id_map = {}
    for page in irelu_item_pages:
        row = tf.transform_irelu_item(page)
        irelu_item_id_map[row["notion_id"]] = upsert(conn, "irelu_items", "notion_id", row)
    print(f"irelu_items: {len(irelu_item_id_map)}件")

    link_count = 0
    for page in irelu_item_pages:
        irelu_item_id = irelu_item_id_map[page["id"]]
        link_rows = []
        for r in tf.transform_irelu_item_links(page):
            irelu_product_id = irelu_product_id_map.get(r["irelu_product_notion_id"])
            if irelu_product_id is None:
                warnings.append(f"irelu_item_links参照切れ: {page['id']} -> {r['irelu_product_notion_id']}")
                continue
            link_rows.append({"irelu_item_id": irelu_item_id, "irelu_product_id": irelu_product_id})
        replace_children(conn, "irelu_item_links", "irelu_item_id", irelu_item_id, link_rows)
        link_count += len(link_rows)
    print(f"irelu_item_links: {link_count}件")

    conn.commit()
    conn.close()

    # --- レポート出力 ---
    lines = ["# ETL load.py 実行レポート\n\n"]
    lines.append(f"## カテゴリ未設定でスキップした商品（{len(skipped_no_category)}件）\n\n")
    if skipped_no_category:
        lines.append("| notion_id | 商品名 |\n|---|---|\n")
        for item in skipped_no_category:
            lines.append(f"| {item['notion_id']} | {item['name']} |\n")
    else:
        lines.append("なし\n")
    lines.append(f"\n## 警告（{len(warnings)}件）\n\n")
    if warnings:
        for w in warnings:
            lines.append(f"- {w}\n")
    else:
        lines.append("なし\n")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"\nレポートを出力しました: {REPORT_PATH}")
    print(f"カテゴリ未設定スキップ: {len(skipped_no_category)}件, 警告: {len(warnings)}件")


if __name__ == "__main__":
    main()
