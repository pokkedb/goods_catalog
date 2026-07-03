-- ============================================================
-- 商品マスタ SQLite移行スキーマ (v1)
-- 対象: 商品DB + 密結合する周辺17DB相当（マスタ / カテゴリ拡張 / irelu拡張）
-- 対象外: 投稿・ブログ・TIPS・セレクト・YouTube・アンケート等の
--         コンテンツ生成系9DB（Notionに残置し、product_id/notion_idで参照する）
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. マスタテーブル
-- ------------------------------------------------------------

CREATE TABLE brands (
    id    INTEGER PRIMARY KEY,
    notion_id TEXT UNIQUE,          -- 移行トレーサビリティ用。移行完了後は運用上必須ではない
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE makers (
    id    INTEGER PRIMARY KEY,
    notion_id TEXT UNIQUE,
    name  TEXT NOT NULL UNIQUE
);

-- グッズカテゴリDB: スリーブ&カバーの対象グッズ規格マスタ（トレカ、缶バッジ等のサイズ規格）
-- 「グッズサイズ」(Notion formula) は selflink を使ってページ名を埋め込む表示用の合成テキスト
-- （例: 「@文庫本サイズ(縦148mm 横105mm)」）で、実体は width_mm/height_mm のみ。
-- generated column で元のformula表示をほぼ再現できる（末尾のページ名部分は名前をJOINして代替）。
CREATE TABLE goods_categories (
    id           INTEGER PRIMARY KEY,
    notion_id    TEXT UNIQUE,
    name         TEXT NOT NULL,
    width_mm     REAL,             -- 横幅
    height_mm    REAL,             -- 縦幅
    depth_mm     REAL,             -- 「幅」（Phase 0実データ調査で用途確定。37件中3件のみ非空で、値はBlu-rayケース12.5/DVDトールケース12.7/CDケース10.4mm。
                                    -- いずれも横幅・縦幅と一致せず、ディスクケース類の背幅(厚み)の実測値と一致するため「幅」ではなく奥行き=厚みの列と判断。
                                    -- 列名もalt_width_mmからdepth_mmに変更。他34件は非空の横幅/縦幅2軸で十分なカテゴリのため空のまま）
    goods_size_label TEXT GENERATED ALWAYS AS (
                        '(縦' || COALESCE(CAST(height_mm AS TEXT), '') ||
                        'mm 横' || COALESCE(CAST(width_mm AS TEXT), '') || 'mm)'
                     ) VIRTUAL      -- Notion「グッズサイズ」formulaの数値部分の再現
);

-- goods_categories.対象商品 (multi_select) の正規化
CREATE TABLE goods_category_targets (
    goods_category_id INTEGER NOT NULL REFERENCES goods_categories(id) ON DELETE CASCADE,
    target_item        TEXT NOT NULL,   -- 例: 'トレカ', '缶バッジ44mm', 'ましかくフォト' 等
    PRIMARY KEY (goods_category_id, target_item)
);

-- goods_categories.selflink（自己参照relation）の正規化。Phase 0実データ調査で用途確定:
-- 37件全件がselflinkを持ち、35件は自分自身のみを指す。これは「グッズサイズ」formulaが
-- 自分自身のページ名を表示に埋め込むためのNotion側の実装上のテクニック（実質的な多対多関連ではない）。
-- 例外的に2件（ウエハースシールサイズ⇄44mm缶バッジサイズ）が互いを指しており原因不明のため、
-- データとしては削らずそのままこのテーブルに保持する。
CREATE TABLE goods_category_selflinks (
    goods_category_id     INTEGER NOT NULL REFERENCES goods_categories(id) ON DELETE CASCADE,
    linked_goods_category_id INTEGER NOT NULL REFERENCES goods_categories(id) ON DELETE CASCADE,
    PRIMARY KEY (goods_category_id, linked_goods_category_id)
);

-- ------------------------------------------------------------
-- 2. 商品コアテーブル
-- ------------------------------------------------------------

CREATE TABLE products (
    id                  INTEGER PRIMARY KEY,
    notion_id           TEXT UNIQUE,     -- 移行元Notion page_id。再同期・監査用に恒久保持を推奨
    name                TEXT NOT NULL,
    category            TEXT NOT NULL CHECK (category IN (
                            'スリーブ＆カバー', 'バインダー＆ファイル', 'リフィル',
                            '収納ケース', 'フレーム', '推し活グッズ', 'デコ素材', 'その他'
                         )),
    brand_id            INTEGER REFERENCES brands(id),
    maker_id            INTEGER REFERENCES makers(id),
    jan_code            TEXT,
    price               INTEGER,          -- 円
    quantity            INTEGER,          -- 入枚数
    unit_price          REAL GENERATED ALWAYS AS (
                            CASE WHEN quantity > 0 THEN ROUND(CAST(price AS REAL) / quantity, 2) END
                         ) VIRTUAL,        -- Notion側 formula「一枚単価」の再現。保存不要・都度算出
    pocket_count        INTEGER,
    pocket_unit_price   REAL GENERATED ALWAYS AS (
                            CASE WHEN pocket_count > 0 THEN ROUND(CAST(price AS REAL) / pocket_count, 2) END
                         ) VIRTUAL,        -- Notion側 formula「ポケット単価」の再現

    -- 外寸・内寸・ポケット寸法（すべてmm）
    outer_width_mm      REAL,
    outer_height_mm     REAL,
    outer_depth_mm      REAL,
    outer_height2_mm    REAL,   -- Notion「外寸高さ」（縦とは別列として存在。フレーム等で使用）
    spine_width_mm       REAL,   -- 背幅
    inner_width_mm       REAL,
    inner_height_mm      REAL,
    inner_depth_mm        REAL,
    inner_height2_mm      REAL,  -- Notion「内寸高さ」
    pocket_inner_width_mm  REAL,
    pocket_inner_height_mm REAL,
    thickness_mm          REAL,
    weight_g               REAL,

    free_description     TEXT,   -- 特徴自由記述
    concerns              TEXT,   -- 懸念点
    image_filename          TEXT,   -- Notion「画像ファイル名」(rich_text)。サンプルでは空が多いが実体プロパティのため保持
    blog_url               TEXT,   -- Notion「ブログURL」(micosblogをrollupした値)
    micosblog_notion_id      TEXT,   -- Notion「micosblog」relation実体。コンテンツ生成系DB(Notion残置)との紐付けキー
    my_block                TEXT,   -- マイブロック（サイト埋め込み用ショートコード相当）
    shortcode                TEXT,
    reference_url             TEXT,
    double_sided_check         INTEGER NOT NULL DEFAULT 0 CHECK (double_sided_check IN (0,1)),

    generate_flag              INTEGER NOT NULL DEFAULT 0 CHECK (generate_flag IN (0,1)),
    created_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_products_category  ON products(category);
CREATE INDEX idx_products_jan_code  ON products(jan_code);
CREATE INDEX idx_products_brand     ON products(brand_id);
CREATE INDEX idx_products_maker     ON products(maker_id);

-- 商品画像（files プロパティの正規化。複数枚対応）
CREATE TABLE product_images (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    source_url  TEXT NOT NULL,     -- Notion/Dropbox上の元URL。再取得(load.py再実行)時の同一性判定キー。値は不変
    url         TEXT NOT NULL,     -- 表示用URL。新規行の初期値はsource_urlと同じだが、download_images.py実行後は
                                    -- ローカルパスに書き換わる。load.pyはsource_url一致の既存行のurlを上書きしないため、
                                    -- 再実行してもダウンロード済み画像が消えない
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_product_images_product ON product_images(product_id);
CREATE UNIQUE INDEX idx_product_images_source_url ON product_images(product_id, source_url);

-- 特徴タグ（特徴1_見た目 〜 特徴6_購入対象者 の multi_select を正規化）
CREATE TABLE product_features (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    group_no    INTEGER NOT NULL CHECK (group_no BETWEEN 1 AND 6),
    -- 1:見た目 2:実用性 3:利用シーン 4:素材 5:カラー 6:購入対象者
    tag         TEXT NOT NULL
);
CREATE INDEX idx_product_features_product ON product_features(product_id, group_no);
CREATE INDEX idx_product_features_tag     ON product_features(group_no, tag);  -- タグ横断検索用

-- ------------------------------------------------------------
-- 3. カテゴリ別拡張テーブル（固有プロパティを持つカテゴリのみサブテーブル化）
--    収納ケース／デコ素材／その他 は固有列を持たないため products.category で判別し、
--    空のサブテーブルは作らない（Notion側の実データでも属性なしを確認済み）
-- ------------------------------------------------------------

CREATE TABLE sleeve_covers (
    product_id         INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    sleeve_type        TEXT CHECK (sleeve_type IN (
                           'ソフトタイプ','ハードタイプ','PVC','硬質ケース','その他','テープ付き','超ハードタイプ'
                        )),
    goods_category_id  INTEGER REFERENCES goods_categories(id)
);

CREATE TABLE binder_files (
    product_id     INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    file_standard  TEXT CHECK (file_standard IN (
                        'ポケット型ファイル','マガジン対応','リング式バインダー','クリアファイル型'
                    ))
);

-- 注記: Notion「リフィル」DBには「ロールアップ」という名前の列が別途あるが、
-- 参照元(relation_property/target)が「1ポケ単価」列と完全に同一（=商品DB.ポケット単価の重複参照）。
-- Notion側の設定ミスによる重複列と判断し、対応するSQLite列は作らない
-- （値は products.pocket_unit_price で完全に再現される。実データでも欠損以外は完全一致することを確認予定）。
CREATE TABLE refills (
    product_id           INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    pocket_count_label    TEXT,   -- Notion「リフィルポケット数」select。表記ゆれが大きいためselectの生値を保持
    refill_standard        TEXT    -- Notion「リフィル規格」select（A4 30穴 等）
);

CREATE TABLE frames (
    product_id      INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    has_stand       INTEGER CHECK (has_stand IN (0,1)),
    has_wall_hook   INTEGER CHECK (has_wall_hook IN (0,1))
);

CREATE TABLE oshi_goods (
    product_id              INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    subcategory              TEXT CHECK (subcategory IN (
                                 'アクスタケース','うちわケース','トレカケース','ぬいぐるみ関連','ペンライトケース',
                                 '推し活トート','推し活ポーチ','推し活ファイル','その他','缶バッジケース',
                                 'カラビナ','推し活手帳','痛バ'
                              )),
    has_hanging_hardware      INTEGER CHECK (has_hanging_hardware IN (0,1)),  -- 吊り下げ金具
    has_charm_hole             INTEGER CHECK (has_charm_hole IN (0,1)),        -- チャーム用穴
    capacity_estimate           INTEGER                                          -- 収納可能目安
);

-- ------------------------------------------------------------
-- 4. irelu拡張（irelu_ITEM DB＋4カテゴリDBの統合）
--    irelu独自の「特徴1〜5」「品番」「発売日」は商品の中でireluブランド分にのみ1:1で付与される
-- ------------------------------------------------------------

CREATE TABLE irelu_products (
    id             INTEGER PRIMARY KEY,
    notion_id      TEXT UNIQUE,
    product_id     INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    category_type  TEXT NOT NULL CHECK (category_type IN ('refill','binder_file','sleeve','other')),
    model_number   TEXT,      -- 品番
    release_date   TEXT,      -- 発売日 (YYYY-MM-DD)
    generate_flag  INTEGER NOT NULL DEFAULT 0 CHECK (generate_flag IN (0,1))
);

CREATE TABLE irelu_features (
    id                INTEGER PRIMARY KEY,
    irelu_product_id  INTEGER NOT NULL REFERENCES irelu_products(id) ON DELETE CASCADE,
    feature_no        INTEGER NOT NULL CHECK (feature_no BETWEEN 1 AND 5),
    title             TEXT,     -- irelu_特徴N
    description       TEXT      -- irelu_特徴N概要
);
CREATE UNIQUE INDEX idx_irelu_features_unique ON irelu_features(irelu_product_id, feature_no);

-- irelu_ITEM: 媒体別に複数のirelu商品を束ねてコンテンツ生成する単位
-- 商品マスタというよりコンテンツ生成寄りの性質が強いが、今回のスコープ確認で商品マスタ関連に含める合意のため搭載
CREATE TABLE irelu_items (
    id             INTEGER PRIMARY KEY,
    notion_id      TEXT UNIQUE,
    name           TEXT NOT NULL,
    media_type     TEXT CHECK (media_type IN (
                       'micosblog_リフィル','micosblog_スリーブ','micosblog','公式サイト','お知らせ'
                    )),
    generate_flag  INTEGER NOT NULL DEFAULT 0 CHECK (generate_flag IN (0,1))
);

CREATE TABLE irelu_item_links (
    irelu_item_id     INTEGER NOT NULL REFERENCES irelu_items(id) ON DELETE CASCADE,
    irelu_product_id  INTEGER NOT NULL REFERENCES irelu_products(id) ON DELETE CASCADE,
    PRIMARY KEY (irelu_item_id, irelu_product_id)
);

-- ------------------------------------------------------------
-- 5. カテゴリ別ロールアップ再現VIEW
--    Notion側の各カテゴリDBで見えていた「商品DBからのロールアップ込みの一覧」を
--    正規化後もそのまま参照できるようにする。正規化＝データの削除ではなく、
--    実体を一箇所（products）に集約した上でJOINにより完全に再現する、という位置づけ。
--    値は一切失われない。全カテゴリDB分を同一パターンで用意する。
-- ------------------------------------------------------------

CREATE VIEW sleeve_covers_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code, p.price, p.quantity, p.unit_price,
    p.inner_width_mm, p.outer_width_mm, p.outer_height_mm, p.thickness_mm,
    p.created_at, b.name AS brand_name, m.name AS maker_name,
    sc.sleeve_type, gc.name AS goods_category_name, gc.width_mm AS goods_width_mm, gc.height_mm AS goods_height_mm
FROM sleeve_covers sc
JOIN products p ON p.id = sc.product_id
LEFT JOIN brands b ON b.id = p.brand_id
LEFT JOIN makers m ON m.id = p.maker_id
LEFT JOIN goods_categories gc ON gc.id = sc.goods_category_id;

CREATE VIEW binder_files_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code, p.price, p.pocket_count, p.pocket_unit_price,
    p.outer_width_mm, p.outer_height_mm, p.spine_width_mm, p.pocket_inner_width_mm, p.pocket_inner_height_mm,
    p.created_at, b.name AS brand_name, m.name AS maker_name,
    bf.file_standard
FROM binder_files bf
JOIN products p ON p.id = bf.product_id
LEFT JOIN brands b ON b.id = p.brand_id
LEFT JOIN makers m ON m.id = p.maker_id;

CREATE VIEW refills_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code, p.price, p.quantity, p.unit_price, p.pocket_count, p.pocket_unit_price,
    p.outer_width_mm, p.outer_height_mm, p.pocket_inner_width_mm, p.pocket_inner_height_mm,
    p.created_at, m.name AS maker_name,
    r.pocket_count_label, r.refill_standard
FROM refills r
JOIN products p ON p.id = r.product_id
LEFT JOIN makers m ON m.id = p.maker_id;

CREATE VIEW storages_view AS
SELECT
    p.id, p.notion_id, p.name, p.price,
    p.outer_width_mm, p.outer_height_mm, p.outer_depth_mm,
    p.inner_width_mm, p.inner_height_mm, p.inner_depth_mm,
    p.created_at, m.name AS maker_name
FROM products p
LEFT JOIN makers m ON m.id = p.maker_id
WHERE p.category = '収納ケース';

CREATE VIEW frames_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code,
    p.outer_width_mm, p.outer_height_mm, p.outer_height2_mm, p.outer_depth_mm,
    p.created_at, m.name AS maker_name,
    f.has_stand, f.has_wall_hook
FROM frames f
JOIN products p ON p.id = f.product_id
LEFT JOIN makers m ON m.id = p.maker_id;

CREATE VIEW oshi_goods_view AS
SELECT
    p.id, p.notion_id, p.name, p.price,
    p.outer_width_mm, p.outer_height_mm, p.outer_depth_mm,
    p.inner_width_mm, p.inner_height_mm, p.inner_depth_mm, p.pocket_count, p.weight_g,
    p.created_at, b.name AS brand_name, m.name AS maker_name,
    og.subcategory, og.has_hanging_hardware, og.has_charm_hole, og.capacity_estimate
FROM oshi_goods og
JOIN products p ON p.id = og.product_id
LEFT JOIN brands b ON b.id = p.brand_id
LEFT JOIN makers m ON m.id = p.maker_id;

CREATE VIEW deco_materials_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code, p.price, p.quantity,
    p.outer_width_mm, p.outer_height_mm,
    p.created_at, b.name AS brand_name, m.name AS maker_name
FROM products p
LEFT JOIN brands b ON b.id = p.brand_id
LEFT JOIN makers m ON m.id = p.maker_id
WHERE p.category = 'デコ素材';

CREATE VIEW others_view AS
SELECT
    p.id, p.notion_id, p.name, p.jan_code, p.price,
    p.outer_width_mm, p.outer_height_mm,
    p.created_at, m.name AS maker_name
FROM products p
LEFT JOIN makers m ON m.id = p.maker_id
WHERE p.category = 'その他';
