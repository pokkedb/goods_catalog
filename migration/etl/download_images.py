# migration/etl/download_images.py
"""
Phase 1 ETL: product_images テーブルに入っている画像URL（Dropbox共有リンク843件相当 +
Notion添付ファイル署名付きURL85件相当）を /pokke/databases/goods_catalog/media/ へ
ダウンロードし、product_images.url をローカルパス（media/ からの相対パス）に書き換える。

- 事前に load.py を実行し、product_images に元URLが入っていること
- 冪等: url が既にローカルパス（http/httpsで始まらない）の行はスキップするので、
  失敗しても再実行すれば続きからダウンロードできる
- Notion添付ファイルの署名付きURLは約1時間で失効する。失効している場合は
  ダウンロードに失敗するので、その場合は fetch.py で該当DBを再取得してから
  load.py → download_images.py を再実行すること

保存先の相対パス規則: media/{product_id}/{sort_order}.{ext}
（拡張子はContent-TypeまたはURLから判定。判定できない場合は jpg とする）

実行方法（プロジェクトルート /pokke/apps/goods_catalog から）:
    python migration/etl/download_images.py
"""
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

DB_PATH = Path("/pokke/databases/goods_catalog/goods_catalog.db")
MEDIA_DIR = Path("/pokke/databases/goods_catalog/media")
REPORT_PATH = Path(__file__).resolve().parent / "download_images_report.md"

REQUEST_TIMEOUT = 30
RETRY_COUNT = 2
RETRY_WAIT_SEC = 2

CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def guess_ext(url, content_type):
    if content_type:
        ext = CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip().lower())
        if ext:
            return ext
    path = urlparse(url).path
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg", "png", "gif", "webp"):
        return "jpg" if suffix == "jpeg" else suffix
    return "jpg"


def download_one(url):
    """成功時は (bytes, content_type) を返す。失敗時は例外を投げる。"""
    last_exc = None
    for attempt in range(1, RETRY_COUNT + 2):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.content, resp.headers.get("Content-Type")
        except Exception as e:  # noqa: BLE001 - リトライ対象を広く受ける
            last_exc = e
            if attempt <= RETRY_COUNT:
                time.sleep(RETRY_WAIT_SEC)
    raise last_exc


def is_remote(url):
    return url.startswith("http://") or url.startswith("https://")


def main():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute(
        "SELECT id, product_id, url, sort_order FROM product_images ORDER BY product_id, sort_order"
    ).fetchall()

    total = len(rows)
    remote_rows = [r for r in rows if is_remote(r[2])]
    print(f"product_images 総数: {total}件 / うちダウンロード対象(未取得): {len(remote_rows)}件")

    success = 0
    failures = []

    for i, (image_id, product_id, url, sort_order) in enumerate(remote_rows, start=1):
        print(f"[{i}/{len(remote_rows)}] product_id={product_id} sort_order={sort_order} をダウンロード中...", flush=True)
        try:
            content, content_type = download_one(url)
        except Exception as e:  # noqa: BLE001
            failures.append({"image_id": image_id, "product_id": product_id, "url": url, "error": str(e)})
            print(f"  失敗: {e}")
            continue

        ext = guess_ext(url, content_type)
        product_dir = MEDIA_DIR / str(product_id)
        product_dir.mkdir(parents=True, exist_ok=True)
        local_file = product_dir / f"{sort_order}.{ext}"
        local_file.write_bytes(content)

        relative_path = f"{product_id}/{sort_order}.{ext}"
        conn.execute("UPDATE product_images SET url = ? WHERE id = ?", (relative_path, image_id))
        conn.commit()
        success += 1

    conn.close()

    lines = ["# 画像ダウンロード実行レポート\n\n"]
    lines.append(f"- 対象: {len(remote_rows)}件（既にローカル化済みでスキップ: {total - len(remote_rows)}件）\n")
    lines.append(f"- 成功: {success}件\n")
    lines.append(f"- 失敗: {len(failures)}件\n\n")
    if failures:
        lines.append("## 失敗一覧\n\n")
        lines.append("| product_id | url | エラー |\n|---|---|---|\n")
        for f in failures:
            lines.append(f"| {f['product_id']} | {f['url']} | {f['error']} |\n")
        lines.append(
            "\nNotion添付ファイルの署名付きURLは約1時間で失効する。失効が疑われる場合は "
            "fetch.py で対象DBを再取得し、load.py → download_images.py を再実行すること。\n"
        )

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"\n成功: {success}件, 失敗: {len(failures)}件")
    print(f"レポートを出力しました: {REPORT_PATH}")


if __name__ == "__main__":
    main()
