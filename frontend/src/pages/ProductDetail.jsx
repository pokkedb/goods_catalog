import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "../api";
import Combobox from "../components/Combobox";

const MEDIA_BASE = import.meta.env.VITE_API_BASE_URL || "http://192.168.50.78:8123";
const MAX_IMAGES = 1;

const FULLWIDTH_DIGITS = "０１２３４５６７８９";
const HALFWIDTH_DIGITS = "0123456789";
function normalizeDigits(value) {
  if (!value) return value;
  return value.replace(/[０-９]/g, (c) => HALFWIDTH_DIGITS[FULLWIDTH_DIGITS.indexOf(c)]);
}

const EMPTY = {
  name: "", category: "スリーブ＆カバー", brand_name: "", maker_name: "",
  jan_code: "", price: "", quantity: "", pocket_count: "",
  outer_width_mm: "", outer_height_mm: "", outer_depth_mm: "", outer_height2_mm: "",
  spine_width_mm: "", inner_width_mm: "", inner_height_mm: "", inner_depth_mm: "", inner_height2_mm: "",
  pocket_inner_width_mm: "", pocket_inner_height_mm: "", thickness_mm: "", weight_g: "",
  free_description: "", concerns: "", reference_url: "", double_sided_check: false,
  sleeve_type: "", goods_category_id: "", file_standard: "", pocket_count_label: "", refill_standard: "",
  has_stand: false, has_wall_hook: false, subcategory: "", has_hanging_hardware: false, has_charm_hole: false,
  capacity_estimate: "",
  features: [],
  is_irelu: false, irelu_model_number: "", irelu_release_date: "", irelu_features: [],
};

const IRELU_FEATURE_NUMBERS = [1, 2, 3, 4, 5];

const SLEEVE_TYPE_CHOICES = ["ソフトタイプ", "ハードタイプ", "PVC", "硬質ケース", "その他", "テープ付き", "超ハードタイプ"];
const FILE_STANDARD_CHOICES = ["ポケット型ファイル", "マガジン対応", "リング式バインダー", "クリアファイル型"];
const OSHI_SUBCATEGORY_CHOICES = [
  "アクスタケース", "うちわケース", "トレカケース", "ぬいぐるみ関連", "ペンライトケース",
  "推し活トート", "推し活ポーチ", "推し活ファイル", "その他", "缶バッジケース", "カラビナ", "推し活手帳", "痛バ",
];

const NUMBER_FIELDS = [
  "price", "quantity", "pocket_count",
  "outer_width_mm", "outer_height_mm", "outer_depth_mm", "outer_height2_mm",
  "spine_width_mm", "inner_width_mm", "inner_height_mm", "inner_depth_mm", "inner_height2_mm",
  "pocket_inner_width_mm", "pocket_inner_height_mm", "thickness_mm", "weight_g",
  "goods_category_id", "capacity_estimate",
];

// DB側でCHECK制約付きのenum列（<select>で「（未設定）」を選ぶとvalue=""になるが、
// ""はCHECK制約のIN(...)に一致せずSQLiteがエラーになるため、送信前にnullへ変換する必要がある
const NULLABLE_ENUM_FIELDS = ["sleeve_type", "file_standard", "subcategory"];

function Field({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      {children}
    </label>
  );
}

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = !id || id === "new";

  const [form, setForm] = useState(EMPTY);
  const [images, setImages] = useState([]);
  const [brandNames, setBrandNames] = useState([]);
  const [makerNames, setMakerNames] = useState([]);
  const [goodsCategories, setGoodsCategories] = useState([]);
  const [categories, setCategories] = useState([]);
  const [featureGroups, setFeatureGroups] = useState({});
  const [pocketCountLabels, setPocketCountLabels] = useState([]);
  const [refillStandards, setRefillStandards] = useState([]);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    api.get("/brands").then((r) => setBrandNames(r.data.map((b) => b.name)));
    api.get("/makers").then((r) => setMakerNames(r.data.map((m) => m.name)));
    api.get("/goods-categories").then((r) => setGoodsCategories(r.data));
    api.get("/meta/product-categories").then((r) => setCategories(r.data));
    api.get("/meta/feature-groups").then((r) => setFeatureGroups(r.data));
    api.get("/meta/refill-pocket-count-labels").then((r) => setPocketCountLabels(r.data));
    api.get("/meta/refill-standards").then((r) => setRefillStandards(r.data));
    if (!isNew) {
      api.get(`/products/${id}`).then((r) => applyResponseToState(r.data));
    }
  }, [id]);

  // サーバーからの応答（初回取得時・保存直後）をフォーム状態に反映する。
  // 保存直後はbrand/makerの正規化やirelu自動連携などサーバー側で決まる値があるため、
  // 画像だけでなくフォーム全体を必ずレスポンスで上書きする
  const applyResponseToState = (d) => {
    setForm({
      ...EMPTY,
      ...d,
      brand_name: d.brand_name ?? "",
      maker_name: d.maker_name ?? "",
      goods_category_id: d.goods_category_id ?? "",
      features: d.features ?? [],
      irelu_model_number: d.irelu_model_number ?? "",
      irelu_release_date: d.irelu_release_date ?? "",
      irelu_features: d.irelu_features ?? [],
    });
    setImages(d.images ?? []);
  };

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const setTag = (groupNo, value) => {
    setForm((f) => {
      const tags = value.split(/[、,]/).map((t) => t.trim()).filter(Boolean);
      const others = f.features.filter((ft) => ft.group_no !== groupNo);
      return { ...f, features: [...others, ...tags.map((tag) => ({ group_no: groupNo, tag }))] };
    });
  };

  const tagsForGroup = (groupNo) =>
    form.features.filter((f) => f.group_no === groupNo).map((f) => f.tag).join("、");

  const setIreluFeature = (featureNo, key, value) => {
    setForm((f) => {
      const others = f.irelu_features.filter((ft) => ft.feature_no !== featureNo);
      const current = f.irelu_features.find((ft) => ft.feature_no === featureNo) ?? { feature_no: featureNo, title: "", description: "" };
      return { ...f, irelu_features: [...others, { ...current, [key]: value }].sort((a, b) => a.feature_no - b.feature_no) };
    });
  };

  const ireluFeature = (featureNo) =>
    form.irelu_features.find((f) => f.feature_no === featureNo) ?? { title: "", description: "" };

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    const payload = { ...form };
    for (const k of NUMBER_FIELDS) {
      payload[k] = payload[k] === "" ? null : Number(payload[k]);
    }
    for (const k of NULLABLE_ENUM_FIELDS) {
      payload[k] = payload[k] === "" ? null : payload[k];
    }

    try {
      if (isNew) {
        const r = await api.post("/products/", payload);
        navigate(`/products/${r.data.id}`);
      } else {
        const r = await api.put(`/products/${id}`, payload);
        applyResponseToState(r.data);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (e) {
      setError(e.response?.data?.detail ?? "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const deleteProduct = async () => {
    if (!confirm(`「${form.name}」を削除しますか？この操作は取り消せません。`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(`/products/${id}`);
      navigate("/products");
    } catch (e) {
      setError(e.response?.data?.detail ?? "削除に失敗しました");
      setDeleting(false);
    }
  };

  const uploadImage = async (file) => {
    setUploading(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const r = await api.post(`/products/${id}/images`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImages((imgs) => [...imgs, r.data]);
    } catch (e) {
      setUploadError(e.response?.data?.detail ?? "アップロードに失敗しました");
    } finally {
      setUploading(false);
    }
  };

  const deleteImage = async (imageId) => {
    if (!confirm("この画像を削除しますか？")) return;
    try {
      await api.delete(`/products/${id}/images/${imageId}`);
      setImages((imgs) => imgs.filter((img) => img.id !== imageId));
    } catch (e) {
      setUploadError(e.response?.data?.detail ?? "削除に失敗しました");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/products" className="text-xs text-blue-600 hover:underline">← 商品一覧に戻る</Link>
          <h1 className="text-xl font-bold text-gray-800 mt-1">{isNew ? "商品 新規登録" : "商品詳細・編集"}</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "保存中..." : "保存"}
          </button>
          {!isNew && (
            <button
              onClick={deleteProduct}
              disabled={saving || deleting}
              className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-400 text-sm font-medium hover:bg-gray-50 hover:text-gray-600 disabled:opacity-50"
            >
              {deleting ? "削除中..." : "削除"}
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
      {saved && <p className="text-green-700 text-sm bg-green-50 border border-green-200 rounded-lg px-3 py-2">保存しました</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* 左カラム: 画像 */}
        <div className="lg:sticky lg:top-6 space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-bold text-gray-700 mb-3">画像</h2>
            {images.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                {images.map((img) => (
                  <div key={img.id} className="relative group">
                    <img
                      src={`${MEDIA_BASE}/media/${img.url}`}
                      alt=""
                      className="w-full aspect-square object-cover rounded-lg border border-gray-200"
                    />
                    <button
                      type="button"
                      onClick={() => deleteImage(img.id)}
                      title="この画像を削除"
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white text-xs
                                 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity
                                 hover:bg-red-600"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-sm mb-3">画像はまだありません</p>
            )}

            {isNew ? (
              <p className="text-xs text-gray-400 mt-3">画像のアップロードは保存後に行えます</p>
            ) : images.length >= MAX_IMAGES ? (
              <p className="text-xs text-gray-400 mt-3">画像は{MAX_IMAGES}枚まで登録できます（差し替える場合は先に削除してください）</p>
            ) : (
              <label
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) uploadImage(file);
                }}
                className={`mt-3 flex items-center justify-center gap-2 border-2 border-dashed rounded-lg py-4 text-sm cursor-pointer transition-colors ${
                  dragOver ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-600"
                }`}
              >
                {uploading ? "アップロード中..." : "＋ 画像を追加（ドラッグ＆ドロップも可）"}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadImage(file);
                    e.target.value = "";
                  }}
                />
              </label>
            )}
            {uploadError && <p className="text-red-600 text-xs mt-2">{uploadError}</p>}
          </div>
        </div>

        {/* 右カラム: フォーム */}
        <div className="lg:col-span-2 space-y-6">
          {/* 基本情報 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <h2 className="text-sm font-bold text-gray-700">基本情報</h2>
            <Field label="商品名 *">
              <input value={form.name} onChange={(e) => set("name", e.target.value)} className="input" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="カテゴリ *">
                <select value={form.category} onChange={(e) => set("category", e.target.value)} className="input">
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
              <Field label="JANコード（全角数字は自動で半角に変換されます）">
                <input
                  value={form.jan_code ?? ""}
                  onChange={(e) => set("jan_code", normalizeDigits(e.target.value))}
                  className="input"
                  inputMode="numeric"
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="ブランド（候補になければ新規追加されます）">
                <Combobox
                  value={form.brand_name}
                  onChange={(v) => set("brand_name", v)}
                  options={brandNames}
                  placeholder="例: irelu"
                />
              </Field>
              <Field label="発売元（候補になければ新規追加されます）">
                <Combobox
                  value={form.maker_name}
                  onChange={(v) => set("maker_name", v)}
                  options={makerNames}
                  placeholder="例: 大創 と入力すると候補が出ます"
                />
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="価格（円）">
                <input type="number" value={form.price ?? ""} onChange={(e) => set("price", e.target.value)} className="input" />
              </Field>
              <Field label="入枚数">
                <input type="number" value={form.quantity ?? ""} onChange={(e) => set("quantity", e.target.value)} className="input" />
              </Field>
              <Field label="ポケット数">
                <input type="number" value={form.pocket_count ?? ""} onChange={(e) => set("pocket_count", e.target.value)} className="input" />
              </Field>
            </div>
          </div>

          {/* カテゴリ別詳細 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <h2 className="text-sm font-bold text-gray-700">カテゴリ別詳細（{form.category}）</h2>

            {form.category === "スリーブ＆カバー" && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="スリーブタイプ">
                  <select value={form.sleeve_type ?? ""} onChange={(e) => set("sleeve_type", e.target.value)} className="input">
                    <option value="">（未設定）</option>
                    {SLEEVE_TYPE_CHOICES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="対象グッズカテゴリ">
                  <select value={form.goods_category_id ?? ""} onChange={(e) => set("goods_category_id", e.target.value)} className="input">
                    <option value="">（未設定）</option>
                    {goodsCategories.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </Field>
              </div>
            )}

            {form.category === "バインダー＆ファイル" && (
              <Field label="ファイル規格">
                <select value={form.file_standard ?? ""} onChange={(e) => set("file_standard", e.target.value)} className="input">
                  <option value="">（未設定）</option>
                  {FILE_STANDARD_CHOICES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            )}

            {form.category === "リフィル" && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="リフィルポケット数（候補になければ自由入力もできます）">
                  <Combobox
                    value={form.pocket_count_label}
                    onChange={(v) => set("pocket_count_label", v)}
                    options={pocketCountLabels}
                    placeholder="例: 4ポケット"
                  />
                </Field>
                <Field label="リフィル規格（候補になければ自由入力もできます）">
                  <Combobox
                    value={form.refill_standard}
                    onChange={(v) => set("refill_standard", v)}
                    options={refillStandards}
                    placeholder="例: A4 30穴"
                  />
                </Field>
              </div>
            )}

            {form.category === "フレーム" && (
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!form.has_stand} onChange={(e) => set("has_stand", e.target.checked)} />
                  スタンドあり
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!form.has_wall_hook} onChange={(e) => set("has_wall_hook", e.target.checked)} />
                  壁掛けフックあり
                </label>
              </div>
            )}

            {form.category === "推し活グッズ" && (
              <div className="space-y-4">
                <Field label="推し活グッズカテゴリ">
                  <select value={form.subcategory ?? ""} onChange={(e) => set("subcategory", e.target.value)} className="input">
                    <option value="">（未設定）</option>
                    {OSHI_SUBCATEGORY_CHOICES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </Field>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={!!form.has_hanging_hardware} onChange={(e) => set("has_hanging_hardware", e.target.checked)} />
                    吊り下げ金具あり
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={!!form.has_charm_hole} onChange={(e) => set("has_charm_hole", e.target.checked)} />
                    チャーム用穴あり
                  </label>
                </div>
                <Field label="収納可能目安">
                  <input type="number" value={form.capacity_estimate ?? ""} onChange={(e) => set("capacity_estimate", e.target.value)} className="input" />
                </Field>
              </div>
            )}

            {["収納ケース", "デコ素材", "その他"].includes(form.category) && (
              <p className="text-gray-400 text-sm">このカテゴリに固有の項目はありません</p>
            )}
          </div>

          {/* サイズ情報（開いた状態） */}
          <details open className="bg-white rounded-xl border border-gray-200 p-6">
            <summary className="text-sm font-bold text-gray-700 cursor-pointer">サイズ情報（すべてmm）</summary>
            <div className="grid grid-cols-3 gap-4 mt-4">
              {[
                ["outer_width_mm", "外寸横"], ["outer_height_mm", "外寸縦"], ["outer_depth_mm", "外寸奥行"],
                ["outer_height2_mm", "外寸高さ"], ["spine_width_mm", "背幅"],
                ["inner_width_mm", "内寸横"], ["inner_height_mm", "内寸縦"], ["inner_depth_mm", "内寸奥行"],
                ["inner_height2_mm", "内寸高さ"],
                ["pocket_inner_width_mm", "ポケット内寸横"], ["pocket_inner_height_mm", "ポケット内寸縦"],
                ["thickness_mm", "厚さ"], ["weight_g", "重さ(g)"],
              ].map(([key, label]) => (
                <Field key={key} label={label}>
                  <input type="number" step="0.01" value={form[key] ?? ""} onChange={(e) => set(key, e.target.value)} className="input" />
                </Field>
              ))}
            </div>
          </details>

          {/* irelu専用情報（irelu連携商品のみ表示） */}
          {form.is_irelu && (
            <div className="rounded-xl border border-gray-200 p-6 space-y-4" style={{ backgroundColor: "#D4E1E8" }}>
              <h2 className="text-sm font-bold text-gray-700">irelu専用情報</h2>
              <div className="grid grid-cols-2 gap-4">
                <Field label="品番">
                  <input
                    value={form.irelu_model_number ?? ""}
                    onChange={(e) => set("irelu_model_number", e.target.value)}
                    className="input"
                  />
                </Field>
                <Field label="発売日">
                  <input
                    type="date"
                    value={form.irelu_release_date ?? ""}
                    onChange={(e) => set("irelu_release_date", e.target.value)}
                    className="input"
                  />
                </Field>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-medium text-gray-500">特徴（最大5つ）</p>
                {IRELU_FEATURE_NUMBERS.map((no) => (
                  <div key={no} className="grid grid-cols-3 gap-3 items-start">
                    <input
                      value={ireluFeature(no).title ?? ""}
                      onChange={(e) => setIreluFeature(no, "title", e.target.value)}
                      placeholder={`特徴${no} タイトル`}
                      className="input"
                    />
                    <textarea
                      value={ireluFeature(no).description ?? ""}
                      onChange={(e) => setIreluFeature(no, "description", e.target.value)}
                      placeholder={`特徴${no} 概要`}
                      className="input col-span-2"
                      rows={4}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 特徴タグ（閉じた状態） */}
          <details className="bg-white rounded-xl border border-gray-200 p-6">
            <summary className="text-sm font-bold text-gray-700 cursor-pointer">特徴タグ</summary>
            <div className="space-y-4 mt-4">
              <p className="text-xs text-gray-400">読点・カンマ区切りで複数入力できます</p>
              {Object.entries(featureGroups).map(([groupNo, label]) => (
                <Field key={groupNo} label={label}>
                  <input
                    value={tagsForGroup(Number(groupNo))}
                    onChange={(e) => setTag(Number(groupNo), e.target.value)}
                    className="input"
                    placeholder="例: かわいい、シンプル"
                  />
                </Field>
              ))}
            </div>
          </details>

          {/* その他（閉じた状態） */}
          <details className="bg-white rounded-xl border border-gray-200 p-6">
            <summary className="text-sm font-bold text-gray-700 cursor-pointer">その他</summary>
            <div className="space-y-4 mt-4">
              <Field label="特徴自由記述">
                <textarea value={form.free_description ?? ""} onChange={(e) => set("free_description", e.target.value)} className="input" rows={3} />
              </Field>
              <Field label="懸念点">
                <textarea value={form.concerns ?? ""} onChange={(e) => set("concerns", e.target.value)} className="input" rows={2} />
              </Field>
              <Field label="参考URL">
                <input value={form.reference_url ?? ""} onChange={(e) => set("reference_url", e.target.value)} className="input" />
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!form.double_sided_check} onChange={(e) => set("double_sided_check", e.target.checked)} />
                両面チェック
              </label>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
