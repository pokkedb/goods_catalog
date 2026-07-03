# migration/etl/migrate_001_product_images_source_url.py
"""
1回限りのマイグレーション: product_images に source_url 列を追加する。

背景: load.py は元々 product_images を商品ごとに削除→再挿入していたため、
download_images.py がローカルパスに書き換えた url も load.py の再実行のたびに
消えてしまっていた（毎回928枚を再ダウンロードする羽目になる）。
これを解消するため、Notion上の元URL(source_url、不変のキー)と表示用URL
(url、ダウンロード後はローカルパスになる)を別列に分離した。

このスクリプトは既存DB（まだsource_url列がない）に対して1回だけ実行する。
- 実行時点でproduct_images.urlがすべてリモートURLのまま（未ダウンロード）なら、
  source_url列を追加してurlの値をそのままコピーするだけで良い
- 既にダウンロード済み（urlがローカルパス）の行が混在している場合は、
  そのままではsource_urlを復元できないため、このスクリプトは安全のため中断する
  （その場合は fetch.py → load.py を再実行してNotion元URLに戻してから実行すること）
- 途中（インデックス作成前）で失敗して再実行した場合にも対応できるよう、
  列の有無とインデックスの有無を別々にチェックして再開可能にしている
  （SQLiteのALTER TABLE等のDDLは個別に自動コミットされるため、
  スクリプトが例外で終了していても列追加自体は残っていることがある）

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/migrate_001_product_images_source_url.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("/pokke/databases/goods_catalog/goods_catalog.db")


def index_exists(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name = ?", (name,)
    ).fetchone() is not None


def main():
    conn = sqlite3.connect(DB_PATH)

    if index_exists(conn, "idx_product_images_source_url"):
        print("マイグレーション済みです（idx_product_images_source_url が既に存在）。")
        conn.close()
        return

    columns = [row[1] for row in conn.execute("PRAGMA table_info(product_images)").fetchall()]
    if "source_url" not in columns:
        conn.execute("ALTER TABLE product_images ADD COLUMN source_url TEXT")
        conn.commit()
        print("source_url列を追加しました。")

    # 列が前回実行分で既に存在していても、バックフィル(UPDATE)はDDLと違って
    # 自動コミットされないため、前回が失敗していれば source_url が NULL のまま
    # 残っている可能性がある。列の有無ではなくNULLの有無で判定する。
    null_count = conn.execute(
        "SELECT COUNT(*) FROM product_images WHERE source_url IS NULL"
    ).fetchone()[0]
    if null_count:
        non_remote = conn.execute(
            "SELECT COUNT(*) FROM product_images WHERE source_url IS NULL AND url NOT LIKE 'http%'"
        ).fetchone()[0]
        if non_remote:
            conn.close()
            raise RuntimeError(
                f"{non_remote}件がローカルパス済みのurlを持っています。"
                "source_urlを復元できないため中断します。"
                "fetch.py → load.py を再実行してurlをNotion元URLに戻してから再実行してください。"
            )
        conn.execute("UPDATE product_images SET source_url = url WHERE source_url IS NULL")
        conn.commit()
        print(f"source_urlが未設定だった{null_count}件をurlの値でバックフィルしました。")
    else:
        print("source_urlは全件設定済みです。バックフィルはスキップします。")

    # (product_id, url) が完全一致する重複行を削除（idが最小の1件だけ残す）。
    # カテゴリ別DB側に同一画像を持つ重複レコードが残っていたことが原因と判明している。
    dup_rows = conn.execute(
        """
        SELECT product_id, url, COUNT(*) c FROM product_images
        GROUP BY product_id, url HAVING c > 1
        """
    ).fetchall()
    if dup_rows:
        print(f"重複行が{len(dup_rows)}組見つかりました。最小idの1件を残して削除します。")
        for product_id, url, _ in dup_rows:
            ids = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM product_images WHERE product_id = ? AND url = ? ORDER BY id",
                    (product_id, url),
                ).fetchall()
            ]
            for image_id in ids[1:]:
                conn.execute("DELETE FROM product_images WHERE id = ?", (image_id,))
            print(f"  product_id={product_id}: {len(ids)}件 -> 1件に統合 ({url[:60]}...)")
        conn.commit()

    conn.execute(
        "CREATE UNIQUE INDEX idx_product_images_source_url ON product_images(product_id, source_url)"
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM product_images").fetchone()[0]
    print(f"マイグレーション完了。product_images: {count}件。")
    conn.close()


if __name__ == "__main__":
    main()
