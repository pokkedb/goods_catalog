# Phase 1 ETL 整合性検証レポート

## 1. Notion側件数とSQLite側件数の突合

| 対象 | Notion側件数 | SQLite側件数 | 差分の説明 |
|---|---:|---:|---|
| brand_db -> brands | 21 | 21 | 一致 |
| maker_db -> makers | 165 | 165 | 一致 |
| goods_category_db -> goods_categories | 37 | 37 | 一致 |
| irelu_item_db -> irelu_items | 1 | 1 | 一致 |
| product_db -> products | 1037 | 1026 | カテゴリ未設定11件を除くと1026件 = 一致（期待通り） |
| sleeve_cover_db -> sleeve_covers | 214（商品DB紐付きは213） | 207 | **不一致（要調査、商品側スキップ等の可能性）** |
| binder_file_db -> binder_files | 88（商品DB紐付きは88） | 88 | 一致 |
| refill_db -> refills | 203（商品DB紐付きは202） | 201 | **不一致（要調査、商品側スキップ等の可能性）** |
| frame_db -> frames | 84（商品DB紐付きは84） | 84 | 一致 |
| oshi_goods_db -> oshi_goods | 323（商品DB紐付きは322） | 320 | **不一致（要調査、商品側スキップ等の可能性）** |
| irelu_refill_db -> irelu_products(refill) | 22（商品DB紐付きは22） | 22 | 一致 |
| irelu_binder_file_db -> irelu_products(binder_file) | 6（商品DB紐付きは6） | 6 | 一致 |
| irelu_sleeve_db -> irelu_products(sleeve) | 19（商品DB紐付きは19） | 19 | 一致 |
| irelu_other_db -> irelu_products(other) | 2（商品DB紐付きは2） | 2 | 一致 |

## 2. 外部キー参照切れ（PRAGMA foreign_key_check）

違反なし

## 3. NOT NULL/CHECK制約サニティチェック

SQLiteはINSERT時に制約を強制するため、load.pyが正常終了していれば通常は違反ゼロのはず。load.py側の変換ロジックにバグがないかを独立の経路で再確認する。

| チェック内容 | 違反件数 |
|---|---:|
| products.name が空 | 0 |
| products.category がCHECK制約のenum外 | 0 |
| products.double_sided_check が0/1以外 | 0 |
| products.generate_flag が0/1以外 | 0 |
| products.created_at が空 | 0 |
| irelu_products.category_type がCHECK制約のenum外 | 0 |
| product_features.group_no が1〜6の範囲外 | 0 |
| irelu_features.feature_no が1〜5の範囲外 | 0 |
| product_images.url が空 | 0 |
| irelu_products.product_id が重複（1:1のはず） | 0 |

**すべて違反なし。**

## 4. カテゴリ未設定でスキップされた商品

11件

| notion_id | 商品名 |
|---|---|
| 25059857-726b-80ac-87f2-c0bbd9adcba7 | カードケースキーホルダーカップケーキ柄 |
| 23559857-726b-8025-b8cc-f4192f4e0f62 | ポケットが選べるシリーズ専用リフィル　A4ワイド用6ポケット |
| 1ab59857-726b-8143-99eb-dff504cf6e9e | 推し活トートバッグG,B,P |
| 1ab59857-726b-8181-8ca4-df43d5b772d9 | リボン付L版フォトキーフォルダー |
| 1ab59857-726b-810d-8c1e-e4d2e40e2531 | うちわカバー |
| 1ab59857-726b-816d-b856-e7d3fb21ed38 | Keptフェイブペンケース |
| 1ab59857-726b-818c-a214-e89e0bd56db5 | うちわカバー |
| 1ab59857-726b-81a6-8be7-f463e561919b | アクスタケース用EVAシート二枚入 |
| 1ab59857-726b-8158-992f-f3ebe041288f | 6リング用ジッパーケースリフィル |
| 1ab59857-726b-8128-a8aa-fb3fa40fad11 | アクリルフレームスタンド |
| 1ab59857-726b-8175-90c1-f41d47d43787 | マグネットカードローダー |

これらはNotion側で8カテゴリのいずれのrelationも設定されていないため、`products.category`のCHECK制約を満たせずSQLiteに未投入。Notion側でカテゴリを設定してから fetch.py → load.py を再実行するか、対象外として扱うかを判断すること。

