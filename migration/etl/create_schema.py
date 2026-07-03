# migration/etl/create_schema.py
"""
Phase 1 ETL: migration/schema.sql を実DB(/pokke/databases/goods_catalog/goods_catalog.db)へ適用する。

既にテーブルが作成済みの場合は何もしない（再実行しても安全）。
まっさらな状態から作り直したい場合は、先にDBファイル自体を手動で削除してから実行する。

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/create_schema.py
"""
import sqlite3
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _ROOT / "migration" / "schema.sql"

DB_DIR = Path("/pokke/databases/goods_catalog")
DB_PATH = DB_DIR / "goods_catalog.db"
MEDIA_DIR = DB_DIR / "media"


def main():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
        )
        if cur.fetchone():
            print(f"{DB_PATH} には既に products テーブルが存在します。スキーマ適用をスキップします。")
            return

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
        print(f"スキーマを適用しました: {DB_PATH}")

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        views = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        print(f"テーブル数: {len(tables)}, VIEW数: {len(views)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
