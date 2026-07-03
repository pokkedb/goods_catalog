# migration/etl/fetch.py
"""
Phase 1 ETL: 商品マスタ関連17DB相当をNotion APIから全件取得し、
migration/etl/raw_dump/ 配下にJSONで保存する。

対象17DB:
  商品DB / グッズカテゴリDB / カテゴリ別8DB / ブランドDB / 発売元DB / irelu関連5DB

load.py がこのJSONを読み込んでSQLiteへ変換・投入する。

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/fetch.py
"""
import sys
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(_ROOT / "legacy"))  # notion_lib は legacy/ 配下に移動済み

from notion_lib.api.notion_client import NotionClient
import notion_lib.config as config

OUTPUT_DIR = Path(__file__).resolve().parent / "raw_dump"

TARGET_DBS = {
    "product_db": config.DATABASE_MAPPING[config.PRODUCT_DB],
    "goods_category_db": config.DATABASE_MAPPING[config.GOODS_CATEGORY_DB],
    "sleeve_cover_db": config.DATABASE_MAPPING[config.SLEEVE_COVER_DB],
    "binder_file_db": config.DATABASE_MAPPING[config.BINDER_FILE_DB],
    "refill_db": config.DATABASE_MAPPING[config.REFILL_DB],
    "storage_db": config.DATABASE_MAPPING[config.STORAGE_DB],
    "frame_db": config.DATABASE_MAPPING[config.FRAME_DB],
    "oshi_goods_db": config.DATABASE_MAPPING[config.OSHI_GOODS_DB],
    "deco_material_db": config.DATABASE_MAPPING[config.DECO_MATERIAL_DB],
    "other_db": config.DATABASE_MAPPING[config.OTHER_DB],
    "brand_db": config.DATABASE_MAPPING[config.BRAND_DB],
    "maker_db": config.DATABASE_MAPPING[config.MAKER_DB],
    "irelu_refill_db": config.IRELU_DB_MAPPING[config.IRELU_REFILL_DB],
    "irelu_binder_file_db": config.IRELU_DB_MAPPING[config.IRELU_BINDER_FILE_DB],
    "irelu_sleeve_db": config.IRELU_DB_MAPPING[config.IRELU_SLEEVE_DB],
    "irelu_other_db": config.IRELU_DB_MAPPING[config.IRELU_OTHER_DB],
    "irelu_item_db": config.IRELU_DB_MAPPING[config.IRELU_ITEM_DB],
}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = NotionClient()

    total_dbs = len(TARGET_DBS)
    summary = {}
    for i, (key, db_id) in enumerate(TARGET_DBS.items(), start=1):
        print(f"\n[{i}/{total_dbs}] {key} ({db_id}) の取得を開始...", flush=True)
        pages = client.query_all_pages(db_id, label=key)

        out_path = OUTPUT_DIR / f"{key}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=2)

        summary[key] = len(pages)
        print(f"[{i}/{total_dbs}] {key}: {len(pages)}件を {out_path} に保存しました", flush=True)

    print("\n=== 取得件数サマリ ===")
    for key, count in summary.items():
        print(f"{key}: {count}件")
    print(f"\n次は create_schema.py → load.py の順で実行してください:\n"
          f"  python migration/etl/create_schema.py\n"
          f"  python migration/etl/load.py")


if __name__ == "__main__":
    main()
