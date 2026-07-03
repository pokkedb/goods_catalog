# migration/phase0/analyze.py
"""
Phase 0 調査用: dump_databases.py が生成した raw_dump/*.json を読み込み、
残タスクの判断材料となるレポート（report.md）とCSVを生成する。

集計内容:
  1. 商品DB全件のサマリ（件数・カテゴリ別内訳）＋ 商品DB.csv 出力
  2. 価格・JANコード・サイズ系プロパティの欠損率（全体／カテゴリ別）
  3. 商品DBの「画像ファイル名」(rich_text) の非空率
  4. goods_categories の 横幅／縦幅／幅 の実データ一覧（用途判断用）
  5. goods_categories.selflink（自己参照）の実データ一覧
  6. カテゴリ別8DBの select 型プロパティの値バリエーション（表記ゆれ調査）

判断（正規化するか／NOT NULLにするか等）はこのレポートを見て人間・Claude側で行う。
このスクリプトはあくまで実データの集計のみを行う。

実行方法（プロジェクトルート /pokke/apps/goods_catalog から。先に dump_databases.py を実行しておくこと）:
    python migration/phase0/analyze.py
"""
import sys
import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(_ROOT))

RAW_DIR = Path(__file__).resolve().parent / "raw_dump"
REPORT_PATH = Path(__file__).resolve().parent / "report.md"
PRODUCT_CSV_PATH = Path(__file__).resolve().parent / "product_db.csv"

CATEGORY_RELATION_PROPS = [
    "スリーブ＆カバー", "バインダー＆ファイル", "リフィル",
    "収納ケース", "フレーム", "推し活グッズ", "デコ素材", "その他",
]

PRODUCT_MISSING_CHECK_FIELDS = [
    "価格", "JANコード", "入枚数", "ポケット数",
    "外寸横", "外寸縦", "外寸奥行", "外寸高さ", "背幅",
    "内寸横", "内寸縦", "内寸奥行", "内寸高さ",
    "ポケット内寸横", "ポケット内寸縦", "厚さ", "重さ",
]


def load(key):
    path = RAW_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} が見つかりません。先に dump_databases.py を実行してください。"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_title(page):
    for prop in page["properties"].values():
        if prop["type"] == "title":
            arr = prop["title"]
            return arr[0]["plain_text"] if arr else ""
    return ""


def raw_value(prop):
    """Notionプロパティオブジェクトから生値と空判定を返す（表示用の単位付与や除外は行わない）"""
    t = prop["type"]
    if t == "title":
        arr = prop["title"]
        return (arr[0]["plain_text"] if arr else None), (not arr)
    if t == "rich_text":
        arr = prop["rich_text"]
        return (arr[0]["plain_text"] if arr else None), (not arr)
    if t == "number":
        v = prop["number"]
        return v, v is None
    if t == "checkbox":
        return prop["checkbox"], False
    if t == "select":
        s = prop["select"]
        return (s["name"] if s else None), (s is None)
    if t == "multi_select":
        arr = prop["multi_select"]
        return [i["name"] for i in arr], (len(arr) == 0)
    if t == "relation":
        arr = prop["relation"]
        return [i["id"] for i in arr], (len(arr) == 0)
    if t == "url":
        return prop["url"], not prop["url"]
    if t == "date":
        d = prop["date"]
        return (d["start"] if d else None), (d is None)
    if t == "files":
        urls = []
        for fobj in prop["files"]:
            if fobj["type"] == "external":
                urls.append(fobj["external"]["url"])
            elif fobj["type"] == "file":
                urls.append(fobj["file"]["url"])
        return urls, (len(urls) == 0)
    if t == "formula":
        ft = prop["formula"].get("type")
        v = prop["formula"].get(ft)
        return v, (v is None or v == "")
    if t == "created_time":
        return prop["created_time"], False
    if t == "rollup":
        return None, True
    return None, True


def get_prop(page, name):
    return page["properties"].get(name)


def get_category(page):
    for cat in CATEGORY_RELATION_PROPS:
        prop = get_prop(page, cat)
        if prop and prop["type"] == "relation" and prop["relation"]:
            return cat
    return "(判定不能)"


def section_product_summary(products, lines):
    lines.append("## 1. 商品DB全件サマリ\n")
    lines.append(f"- 総件数: **{len(products)}件**\n")

    cat_counter = Counter(get_category(p) for p in products)
    lines.append("- カテゴリ別内訳（商品DB側の8カテゴリrelationで判定）:\n")
    for cat in CATEGORY_RELATION_PROPS + ["(判定不能)"]:
        if cat_counter.get(cat):
            lines.append(f"  - {cat}: {cat_counter[cat]}件\n")
    lines.append("\n")


def section_missing_rates(products, lines):
    lines.append("## 2. 価格・JANコード・サイズ系プロパティの欠損率\n")
    lines.append(
        "NOT NULL制約を付けてよい列／付けてはいけない列の切り分け材料。\n\n"
    )

    total = len(products)
    lines.append("### 全体\n\n")
    lines.append("| プロパティ | 欠損数 | 欠損率 |\n|---|---:|---:|\n")
    overall_missing = {}
    for field in PRODUCT_MISSING_CHECK_FIELDS:
        missing = 0
        for p in products:
            prop = get_prop(p, field)
            if prop is None:
                missing += 1
                continue
            _, is_empty = raw_value(prop)
            if is_empty:
                missing += 1
        overall_missing[field] = missing
        rate = (missing / total * 100) if total else 0
        lines.append(f"| {field} | {missing} | {rate:.1f}% |\n")
    lines.append("\n")

    lines.append("### カテゴリ別\n\n")
    by_cat = defaultdict(list)
    for p in products:
        by_cat[get_category(p)].append(p)

    for cat, plist in by_cat.items():
        lines.append(f"#### {cat}（{len(plist)}件）\n\n")
        lines.append("| プロパティ | 欠損数 | 欠損率 |\n|---|---:|---:|\n")
        for field in PRODUCT_MISSING_CHECK_FIELDS:
            missing = 0
            for p in plist:
                prop = get_prop(p, field)
                if prop is None:
                    missing += 1
                    continue
                _, is_empty = raw_value(prop)
                if is_empty:
                    missing += 1
            rate = (missing / len(plist) * 100) if plist else 0
            lines.append(f"| {field} | {missing} | {rate:.1f}% |\n")
        lines.append("\n")


def section_image_filename(products, lines):
    lines.append("## 3. 商品DB「画像ファイル名」(rich_text) の非空率\n\n")
    total = len(products)
    non_empty = 0
    samples = []
    for p in products:
        prop = get_prop(p, "画像ファイル名")
        if prop is None:
            continue
        value, is_empty = raw_value(prop)
        if not is_empty:
            non_empty += 1
            if len(samples) < 10:
                samples.append((get_title(p), value))
    rate = (non_empty / total * 100) if total else 0
    lines.append(f"- 非空件数: {non_empty} / {total}件（{rate:.1f}%）\n\n")
    if samples:
        lines.append("非空サンプル（最大10件）:\n\n")
        lines.append("| 商品名 | 画像ファイル名 |\n|---|---|\n")
        for name, value in samples:
            lines.append(f"| {name} | {value} |\n")
        lines.append("\n")


def section_goods_categories(goods_categories, lines):
    lines.append("## 4. goods_categories: 横幅／縦幅／幅 の実データ一覧\n\n")
    lines.append(
        "`alt_width_mm`（幅）と横幅／縦幅の使い分けの実態を確認する材料。\n\n"
    )
    lines.append("| 名前 | 横幅 | 縦幅 | 幅 | 幅==横幅? | 幅==縦幅? |\n|---|---:|---:|---:|---|---|\n")

    alt_eq_width = 0
    alt_eq_height = 0
    alt_other = 0
    alt_present = 0

    for p in goods_categories:
        name = get_title(p)
        width, _ = raw_value(get_prop(p, "横幅"))
        height, _ = raw_value(get_prop(p, "縦幅"))
        alt, alt_empty = raw_value(get_prop(p, "幅"))

        eq_w = "○" if (alt is not None and alt == width) else ""
        eq_h = "○" if (alt is not None and alt == height) else ""

        if not alt_empty:
            alt_present += 1
            if alt == width:
                alt_eq_width += 1
            elif alt == height:
                alt_eq_height += 1
            else:
                alt_other += 1

        lines.append(f"| {name} | {width} | {height} | {alt} | {eq_w} | {eq_h} |\n")

    lines.append("\n")
    lines.append(f"- 「幅」が非空の件数: {alt_present} / {len(goods_categories)}件\n")
    lines.append(f"  - うち 横幅と一致: {alt_eq_width}件\n")
    lines.append(f"  - うち 縦幅と一致: {alt_eq_height}件\n")
    lines.append(f"  - うち どちらとも不一致: {alt_other}件\n\n")


def section_selflink(goods_categories, lines):
    lines.append("## 5. goods_categories.selflink（自己参照）の実データ一覧\n\n")

    id_to_name = {p["id"]: get_title(p) for p in goods_categories}

    lines.append("| 名前 | selflink件数 | selflink先 |\n|---|---:|---|\n")
    with_link = 0
    count_dist = Counter()
    for p in goods_categories:
        name = get_title(p)
        prop = get_prop(p, "selflink")
        ids, is_empty = raw_value(prop)
        if is_empty:
            continue
        with_link += 1
        count_dist[len(ids)] += 1
        target_names = ", ".join(id_to_name.get(i, f"(不明:{i})") for i in ids)
        lines.append(f"| {name} | {len(ids)} | {target_names} |\n")

    lines.append("\n")
    lines.append(f"- selflinkを持つレコード: {with_link} / {len(goods_categories)}件\n")
    lines.append("- 1レコードあたりのselflink件数の分布:\n")
    for count, freq in sorted(count_dist.items()):
        lines.append(f"  - {count}件: {freq}レコード\n")
    lines.append("\n")


def section_select_variants(category_dbs, lines):
    lines.append("## 6. カテゴリ別DBのselect型プロパティ: 値バリエーション（表記ゆれ調査）\n\n")
    lines.append(
        "正規化して数値+ラベルに分解するか、生値のまま保持するかの判断材料。\n\n"
    )

    for db_key, pages in category_dbs.items():
        if not pages:
            continue
        # そのDBに存在するselect型プロパティ名を全ページから収集
        select_props = set()
        for p in pages:
            for prop_name, prop in p["properties"].items():
                if prop["type"] == "select":
                    select_props.add(prop_name)

        if not select_props:
            continue

        lines.append(f"### {db_key}\n\n")
        for prop_name in sorted(select_props):
            counter = Counter()
            missing = 0
            for p in pages:
                prop = get_prop(p, prop_name)
                value, is_empty = raw_value(prop) if prop else (None, True)
                if is_empty:
                    missing += 1
                else:
                    counter[value] += 1

            lines.append(f"#### {prop_name}（{len(counter)}種類の値、欠損{missing}件）\n\n")
            lines.append("| 値 | 件数 |\n|---|---:|\n")
            for value, freq in counter.most_common():
                lines.append(f"| {value} | {freq} |\n")
            lines.append("\n")


def export_product_csv(products):
    fields = ["notion_id", "name", "category"] + PRODUCT_MISSING_CHECK_FIELDS + ["画像ファイル名"]
    with open(PRODUCT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for p in products:
            row = [p["id"], get_title(p), get_category(p)]
            for field in PRODUCT_MISSING_CHECK_FIELDS + ["画像ファイル名"]:
                prop = get_prop(p, field)
                value, _ = raw_value(prop) if prop else (None, True)
                row.append(value)
            writer.writerow(row)
    print(f"商品DB CSVを出力しました: {PRODUCT_CSV_PATH}")


def main():
    products = load("product_db")
    goods_categories = load("goods_category_db")

    category_dbs = {}
    for key in [
        "sleeve_cover_db", "binder_file_db", "refill_db", "storage_db",
        "frame_db", "oshi_goods_db", "deco_material_db", "other_db",
    ]:
        category_dbs[key] = load(key)

    lines = ["# Phase 0 実データ調査レポート\n\n"]
    section_product_summary(products, lines)
    section_missing_rates(products, lines)
    section_image_filename(products, lines)
    section_goods_categories(goods_categories, lines)
    section_selflink(goods_categories, lines)
    section_select_variants(category_dbs, lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"レポートを出力しました: {REPORT_PATH}")

    export_product_csv(products)


if __name__ == "__main__":
    main()
