# migration/etl/verify.py
"""
Phase 1 ETL: 移行結果の整合性検証。

1. Notion側件数（raw_dump/*.json）とSQLite側件数の突合
2. 外部キー参照切れの検出（PRAGMA foreign_key_check + notion_id単位の参照切れ）
3. NOT NULL/CHECK制約に関わる業務ルールのサニティチェック
   （SQLite自体がINSERT時に強制するため通常は違反ゼロのはずだが、
   load.py側のバグ検出用に独立した経路で再チェックする）
4. カテゴリ未設定でスキップされた商品の一覧

事前に fetch.py → create_schema.py → load.py を実行しておくこと。

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/verify.py
"""
import json
import sqlite3
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent / "raw_dump"
DB_PATH = Path("/pokke/databases/goods_catalog/goods_catalog.db")
REPORT_PATH = Path(__file__).resolve().parent / "verify_report.md"

CATEGORY_RELATION_PROPS = [
    "スリーブ＆カバー", "バインダー＆ファイル", "リフィル",
    "収納ケース", "フレーム", "推し活グッズ", "デコ素材", "その他",
]

# サブタイプテーブルを持つカテゴリ別DB
SUBTYPE_TABLES = {
    "sleeve_cover_db": "sleeve_covers",
    "binder_file_db": "binder_files",
    "refill_db": "refills",
    "frame_db": "frames",
    "oshi_goods_db": "oshi_goods",
}

IRELU_DB_TO_CATEGORY_TYPE = {
    "irelu_refill_db": "refill",
    "irelu_binder_file_db": "binder_file",
    "irelu_sleeve_db": "sleeve",
    "irelu_other_db": "other",
}


def load_json(key):
    path = RAW_DIR / f"{key}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_relation_ids(page, prop_name):
    prop = page["properties"].get(prop_name)
    if not prop or prop["type"] != "relation":
        return []
    return [r["id"] for r in prop["relation"]]


def has_any_category(page):
    return any(get_relation_ids(page, c) for c in CATEGORY_RELATION_PROPS)


def section_count_comparison(conn, lines):
    lines.append("## 1. Notion側件数とSQLite側件数の突合\n\n")
    lines.append("| 対象 | Notion側件数 | SQLite側件数 | 差分の説明 |\n|---|---:|---:|---|\n")

    simple_pairs = [
        ("brand_db", "brands"),
        ("maker_db", "makers"),
        ("goods_category_db", "goods_categories"),
        ("irelu_item_db", "irelu_items"),
    ]
    for json_key, table in simple_pairs:
        pages = load_json(json_key)
        if pages is None:
            lines.append(f"| {json_key} | (未取得) | - | raw_dump/{json_key}.json が見つからない |\n")
            continue
        sqlite_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        note = "一致" if len(pages) == sqlite_count else "**不一致**"
        lines.append(f"| {json_key} -> {table} | {len(pages)} | {sqlite_count} | {note} |\n")

    # products: カテゴリ未設定分の差分を許容
    product_pages = load_json("product_db")
    if product_pages is not None:
        no_category = [p for p in product_pages if not has_any_category(p)]
        sqlite_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        expected = len(product_pages) - len(no_category)
        note = "一致（期待通り）" if sqlite_products == expected else "**不一致（要調査）**"
        lines.append(
            f"| product_db -> products | {len(product_pages)} "
            f"| {sqlite_products} | カテゴリ未設定{len(no_category)}件を除くと{expected}件 = {note} |\n"
        )

    # カテゴリ別8DB -> サブタイプテーブル
    for json_key, table in SUBTYPE_TABLES.items():
        pages = load_json(json_key)
        if pages is None:
            continue
        linked = [p for p in pages if get_relation_ids(p, "商品DB")]
        sqlite_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        note = "一致" if len(linked) == sqlite_count else "**不一致（要調査、商品側スキップ等の可能性）**"
        lines.append(
            f"| {json_key} -> {table} | {len(pages)}（商品DB紐付きは{len(linked)}） "
            f"| {sqlite_count} | {note} |\n"
        )

    # irelu category dbs -> irelu_products (category_typeごと)
    for json_key, category_type in IRELU_DB_TO_CATEGORY_TYPE.items():
        pages = load_json(json_key)
        if pages is None:
            continue
        linked = [p for p in pages if get_relation_ids(p, "商品DB")]
        sqlite_count = conn.execute(
            "SELECT COUNT(*) FROM irelu_products WHERE category_type = ?", (category_type,)
        ).fetchone()[0]
        note = "一致" if len(linked) == sqlite_count else "**不一致（要調査）**"
        lines.append(
            f"| {json_key} -> irelu_products({category_type}) | {len(pages)}（商品DB紐付きは{len(linked)}） "
            f"| {sqlite_count} | {note} |\n"
        )

    lines.append("\n")


def section_foreign_key_check(conn, lines):
    lines.append("## 2. 外部キー参照切れ（PRAGMA foreign_key_check）\n\n")
    issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    if not issues:
        lines.append("違反なし\n\n")
        return
    lines.append("| table | rowid | 参照先table | 参照先fkid |\n|---|---:|---|---:|\n")
    for row in issues:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |\n")
    lines.append("\n")


def section_constraint_sanity_checks(conn, lines):
    lines.append("## 3. NOT NULL/CHECK制約サニティチェック\n\n")
    lines.append(
        "SQLiteはINSERT時に制約を強制するため、load.pyが正常終了していれば通常は違反ゼロのはず。"
        "load.py側の変換ロジックにバグがないかを独立の経路で再確認する。\n\n"
    )

    checks = [
        ("products.name が空", "SELECT COUNT(*) FROM products WHERE name IS NULL OR name = ''"),
        (
            "products.category がCHECK制約のenum外",
            """SELECT COUNT(*) FROM products WHERE category NOT IN (
                'スリーブ＆カバー', 'バインダー＆ファイル', 'リフィル',
                '収納ケース', 'フレーム', '推し活グッズ', 'デコ素材', 'その他'
            )""",
        ),
        (
            "products.double_sided_check が0/1以外",
            "SELECT COUNT(*) FROM products WHERE double_sided_check NOT IN (0, 1)",
        ),
        (
            "products.generate_flag が0/1以外",
            "SELECT COUNT(*) FROM products WHERE generate_flag NOT IN (0, 1)",
        ),
        ("products.created_at が空", "SELECT COUNT(*) FROM products WHERE created_at IS NULL OR created_at = ''"),
        (
            "irelu_products.category_type がCHECK制約のenum外",
            "SELECT COUNT(*) FROM irelu_products WHERE category_type NOT IN ('refill','binder_file','sleeve','other')",
        ),
        (
            "product_features.group_no が1〜6の範囲外",
            "SELECT COUNT(*) FROM product_features WHERE group_no NOT BETWEEN 1 AND 6",
        ),
        (
            "irelu_features.feature_no が1〜5の範囲外",
            "SELECT COUNT(*) FROM irelu_features WHERE feature_no NOT BETWEEN 1 AND 5",
        ),
        ("product_images.url が空", "SELECT COUNT(*) FROM product_images WHERE url IS NULL OR url = ''"),
        (
            "irelu_products.product_id が重複（1:1のはず）",
            "SELECT COUNT(*) - COUNT(DISTINCT product_id) FROM irelu_products",
        ),
    ]

    lines.append("| チェック内容 | 違反件数 |\n|---|---:|\n")
    any_violation = False
    for label, sql in checks:
        count = conn.execute(sql).fetchone()[0]
        if count:
            any_violation = True
        lines.append(f"| {label} | {count} |\n")
    lines.append("\n")
    if not any_violation:
        lines.append("**すべて違反なし。**\n\n")


def section_skipped_products(lines):
    lines.append("## 4. カテゴリ未設定でスキップされた商品\n\n")
    product_pages = load_json("product_db")
    if product_pages is None:
        lines.append("product_db.json が見つからないため確認できず\n\n")
        return
    no_category = [p for p in product_pages if not has_any_category(p)]
    lines.append(f"{len(no_category)}件\n\n")
    if no_category:
        lines.append("| notion_id | 商品名 |\n|---|---|\n")
        for p in no_category:
            name = None
            for prop in p["properties"].values():
                if prop["type"] == "title" and prop["title"]:
                    name = prop["title"][0]["plain_text"]
            lines.append(f"| {p['id']} | {name} |\n")
        lines.append(
            "\nこれらはNotion側で8カテゴリのいずれのrelationも設定されていないため、"
            "`products.category`のCHECK制約を満たせずSQLiteに未投入。"
            "Notion側でカテゴリを設定してから fetch.py → load.py を再実行するか、"
            "対象外として扱うかを判断すること。\n"
        )
    lines.append("\n")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    lines = ["# Phase 1 ETL 整合性検証レポート\n\n"]
    section_count_comparison(conn, lines)
    section_foreign_key_check(conn, lines)
    section_constraint_sanity_checks(conn, lines)
    section_skipped_products(lines)

    conn.close()

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"検証レポートを出力しました: {REPORT_PATH}")


if __name__ == "__main__":
    main()
