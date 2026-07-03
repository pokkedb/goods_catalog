import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../api";

const MEDIA_BASE = import.meta.env.VITE_API_BASE_URL || "http://192.168.50.78:8123";
const PAGE_SIZE = 60;

export default function ProductList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);

  const [qInput, setQInput] = useState(q);
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  useEffect(() => {
    api.get("/meta/product-categories").then((r) => setCategories(r.data));
  }, []);

  useEffect(() => {
    setQInput(q);
  }, [q]);

  useEffect(() => {
    setLoading(true);
    api
      .get("/products/", {
        params: {
          q: q || undefined,
          category: category || undefined,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        },
      })
      .then((r) => {
        setProducts(r.data.items);
        setTotal(r.data.total);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, category, page]);

  // page/category/検索語をURLに載せることで、ヘッダーの「一覧に戻る」リンクや
  // ブラウザの戻る/進むが正しく機能するようにする（同一パスのままだと遷移が起きない）
  const updateParams = (next) => {
    const merged = { q, category, page: String(page), ...next };
    const params = {};
    if (merged.q) params.q = merged.q;
    if (merged.category) params.category = merged.category;
    if (merged.page && merged.page !== "1") params.page = merged.page;
    setSearchParams(params);
  };

  const search = () => {
    updateParams({ q: qInput, page: "1" });
  };

  const changeCategory = (c) => {
    updateParams({ category: c, page: "1" });
  };

  const goToPage = (p) => {
    const clamped = Math.min(Math.max(p, 1), totalPages);
    updateParams({ page: String(clamped) });
    window.scrollTo(0, 0);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">商品一覧</h1>
        <Link
          to="/products/new"
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          ＋ 新規登録
        </Link>
      </div>

      <div className="flex gap-3">
        <input
          className="input max-w-xs"
          placeholder="商品名・JANコードで検索"
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <select className="input max-w-xs" value={category} onChange={(e) => changeCategory(e.target.value)}>
          <option value="">すべてのカテゴリ</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <button
          onClick={search}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          検索
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">読み込み中...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {products.map((p) => (
            <Link
              key={p.id}
              to={`/products/${p.id}`}
              className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="aspect-square bg-gray-100 flex items-center justify-center">
                {p.thumbnail_url ? (
                  <img
                    src={`${MEDIA_BASE}/media/${p.thumbnail_url}`}
                    alt={p.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span className="text-gray-300 text-xs">画像なし</span>
                )}
              </div>
              <div className="p-3 space-y-1">
                <p className="text-xs text-gray-500">{p.category}</p>
                <p className="text-sm font-medium text-gray-800 line-clamp-2">{p.name}</p>
                <p className="text-xs text-gray-500">
                  {p.brand_name || p.maker_name || "—"}
                </p>
                <p className="text-sm font-bold text-gray-900">
                  {p.price != null ? `¥${p.price.toLocaleString()}` : "—"}
                </p>
              </div>
            </Link>
          ))}
          {products.length === 0 && (
            <p className="text-gray-400 text-sm col-span-full">該当する商品がありません</p>
          )}
        </div>
      )}

      {!loading && total > 0 && (
        <div className="flex flex-col items-center gap-2 pt-2">
          <Pager page={page} totalPages={totalPages} onChange={goToPage} />
          <p className="text-xs text-gray-500">
            全{total.toLocaleString()}件中 {(page - 1) * PAGE_SIZE + 1}〜{Math.min(page * PAGE_SIZE, total)}件を表示
          </p>
        </div>
      )}
    </div>
  );
}

function Pager({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;

  const pageNumbers = [];
  const windowSize = 2;
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || (p >= page - windowSize && p <= page + windowSize)) {
      pageNumbers.push(p);
    } else if (pageNumbers[pageNumbers.length - 1] !== "…") {
      pageNumbers.push("…");
    }
  }

  const btnClass = (active) =>
    `w-8 h-8 rounded-lg text-sm font-medium ${
      active ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
    }`;

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className="px-2 py-1 rounded-lg text-sm text-gray-500 hover:bg-gray-100 disabled:opacity-30"
      >
        ← 前へ
      </button>
      {pageNumbers.map((p, i) =>
        p === "…" ? (
          <span key={`ellipsis-${i}`} className="w-8 h-8 flex items-center justify-center text-gray-400 text-sm">…</span>
        ) : (
          <button key={p} onClick={() => onChange(p)} className={btnClass(p === page)}>
            {p}
          </button>
        )
      )}
      <button
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        className="px-2 py-1 rounded-lg text-sm text-gray-500 hover:bg-gray-100 disabled:opacity-30"
      >
        次へ →
      </button>
    </div>
  );
}
