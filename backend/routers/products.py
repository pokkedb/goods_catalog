import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from PIL import Image
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    Product, ProductImage, ProductFeature, Brand, Maker,
    SleeveCover, BinderFile, Refill, Frame, OshiGoods, IreluProduct, IreluFeature,
)
from schemas.product import (
    ProductResponse, ProductUpdate, ProductCreate, ProductListItem, ProductListResponse, ProductImageOut,
)

router = APIRouter(prefix="/products", tags=["products"])

MEDIA_DIR = Path("/pokke/databases/goods_catalog/media")
UPLOAD_CONTENT_TYPES = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/webp": "webp", "image/gif": "gif",
}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGES_PER_PRODUCT = 1  # フロント側の制限と合わせる（基本1商品1画像の運用のため）
MAX_IMAGE_DIMENSION = 1600  # 長辺がこれを超える場合のみ縮小
JPEG_QUALITY = 80

# カテゴリ名 -> (サブタイプORMクラス, そのカテゴリ固有のペイロードフィールド名一覧)
CATEGORY_SUBTYPE_MAP = {
    "スリーブ＆カバー": (SleeveCover, ["sleeve_type", "goods_category_id"]),
    "バインダー＆ファイル": (BinderFile, ["file_standard"]),
    "リフィル": (Refill, ["pocket_count_label", "refill_standard"]),
    "フレーム": (Frame, ["has_stand", "has_wall_hook"]),
    "推し活グッズ": (OshiGoods, ["subcategory", "has_hanging_hardware", "has_charm_hole", "capacity_estimate"]),
}

# 実データ確認済み: irelu_products に紐づく商品は例外なく全件ブランド名が"irelu"（49/49件）で、
# ブランド"irelu"の商品も例外なく全件irelu_products連携済み。1:1で対応しているため、
# ブランドを"irelu"に設定/解除するだけでirelu連携も自動的に追随させる
IRELU_BRAND_NAME = "irelu"
IRELU_CATEGORY_TYPE_MAP = {
    "スリーブ＆カバー": "sleeve",
    "バインダー＆ファイル": "binder_file",
    "リフィル": "refill",
    "その他": "other",
}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _get_or_create_by_name(db: Session, model_cls, name: str | None):
    """名前の完全一致で既存レコードを探し、なければ新規作成して返す（ブランド/発売元の新規追加用）"""
    if not name or not name.strip():
        return None
    name = name.strip()
    obj = db.query(model_cls).filter(model_cls.name == name).first()
    if obj is None:
        obj = model_cls(name=name)
        db.add(obj)
        db.flush()  # id を確定させる
    return obj


def _to_response(p: Product) -> ProductResponse:
    data = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    data["brand_name"] = p.brand.name if p.brand else None
    data["maker_name"] = p.maker.name if p.maker else None

    subtype_entry = CATEGORY_SUBTYPE_MAP.get(p.category)
    if subtype_entry:
        attr_name = {
            SleeveCover: "sleeve_cover", BinderFile: "binder_file", Refill: "refill",
            Frame: "frame", OshiGoods: "oshi_goods",
        }[subtype_entry[0]]
        subtype_obj = getattr(p, attr_name)
        if subtype_obj:
            for field in subtype_entry[1]:
                data[field] = getattr(subtype_obj, field)
            if isinstance(subtype_obj, SleeveCover) and subtype_obj.goods_category:
                data["goods_category_name"] = subtype_obj.goods_category.name

    data["images"] = sorted(p.images, key=lambda i: i.sort_order)
    data["features"] = p.features

    if p.irelu_product:
        data["is_irelu"] = True
        data["irelu_model_number"] = p.irelu_product.model_number
        data["irelu_release_date"] = p.irelu_product.release_date
        data["irelu_features"] = sorted(p.irelu_product.features, key=lambda f: f.feature_no)
    else:
        data["is_irelu"] = False

    return ProductResponse.model_validate(data)


def _sync_category_subtype(db: Session, product: Product, payload: ProductUpdate):
    """product.category に応じたサブタイプテーブルをupsertし、該当しなくなった旧サブタイプ行は削除する"""
    for other_category, (model_cls, _) in CATEGORY_SUBTYPE_MAP.items():
        if other_category == product.category:
            continue
        stale = db.query(model_cls).filter(model_cls.product_id == product.id).first()
        if stale:
            db.delete(stale)

    subtype_entry = CATEGORY_SUBTYPE_MAP.get(product.category)
    if not subtype_entry:
        return
    model_cls, fields = subtype_entry

    row = db.query(model_cls).filter(model_cls.product_id == product.id).first()
    if row is None:
        row = model_cls(product_id=product.id)
        db.add(row)
    for field in fields:
        setattr(row, field, getattr(payload, field))


def _sync_irelu_link(db: Session, product: Product, brand: Brand | None) -> IreluProduct | None:
    """ブランドが"irelu"かどうかでirelu連携を自動的に作成/解除し、連携後のIreluProduct（未連携ならNone）を返す"""
    category_type = IRELU_CATEGORY_TYPE_MAP.get(product.category)
    should_be_irelu = brand is not None and brand.name == IRELU_BRAND_NAME and category_type is not None

    existing = db.query(IreluProduct).filter(IreluProduct.product_id == product.id).first()

    if should_be_irelu:
        if existing is None:
            existing = IreluProduct(product_id=product.id, category_type=category_type, generate_flag=0)
            db.add(existing)
            db.flush()
        elif existing.category_type != category_type:
            existing.category_type = category_type
        return existing

    if existing is not None:
        db.delete(existing)
    return None


def _apply_payload(db: Session, product: Product, payload: ProductUpdate, is_new: bool):
    base_fields = [
        "name", "category", "jan_code", "price", "quantity",
        "pocket_count", "outer_width_mm", "outer_height_mm", "outer_depth_mm", "outer_height2_mm",
        "spine_width_mm", "inner_width_mm", "inner_height_mm", "inner_depth_mm", "inner_height2_mm",
        "pocket_inner_width_mm", "pocket_inner_height_mm", "thickness_mm", "weight_g",
        "free_description", "concerns", "reference_url",
    ]
    for field in base_fields:
        setattr(product, field, getattr(payload, field))
    product.double_sided_check = 1 if payload.double_sided_check else 0

    brand = _get_or_create_by_name(db, Brand, payload.brand_name)
    maker = _get_or_create_by_name(db, Maker, payload.maker_name)
    product.brand_id = brand.id if brand else None
    product.maker_id = maker.id if maker else None
    product.updated_at = _now_iso()
    if is_new:
        product.created_at = _now_iso()
        product.generate_flag = 0
        db.add(product)
        db.flush()  # product.id を確定させる（サブタイプ・特徴タグのFKに必要）

    _sync_category_subtype(db, product, payload)

    db.query(ProductFeature).filter(ProductFeature.product_id == product.id).delete()
    for f in payload.features:
        db.add(ProductFeature(product_id=product.id, group_no=f.group_no, tag=f.tag))

    # ブランドが"irelu"かどうかでirelu連携を自動的に作成/解除する（実データで1:1対応を確認済み）
    irelu_product = _sync_irelu_link(db, product, brand)
    if irelu_product is not None:
        irelu_product.model_number = payload.irelu_model_number
        irelu_product.release_date = payload.irelu_release_date
        db.query(IreluFeature).filter(
            IreluFeature.irelu_product_id == irelu_product.id
        ).delete()
        for f in payload.irelu_features:
            if not f.title and not f.description:
                continue
            db.add(IreluFeature(
                irelu_product_id=irelu_product.id,
                feature_no=f.feature_no, title=f.title, description=f.description,
            ))


@router.get("/", response_model=ProductListResponse)
def list_products(
    q: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if q:
        query = query.filter(or_(Product.name.contains(q), Product.jan_code.contains(q)))
    if category:
        query = query.filter(Product.category == category)

    total = query.count()
    products = (
        query.options(joinedload(Product.brand), joinedload(Product.maker), joinedload(Product.images))
        .order_by(Product.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for p in products:
        thumbnail = min(p.images, key=lambda i: i.sort_order).url if p.images else None
        items.append(ProductListItem(
            id=p.id, name=p.name, category=p.category,
            brand_name=p.brand.name if p.brand else None,
            maker_name=p.maker.name if p.maker else None,
            price=p.price, jan_code=p.jan_code, thumbnail_url=thumbnail,
        ))
    return ProductListResponse(items=items, total=total)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    return _to_response(p)


@router.post("/", response_model=ProductResponse)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product()
    _apply_payload(db, product, payload, is_new=True)
    db.commit()
    db.refresh(product)
    return _to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    _apply_payload(db, product, payload, is_new=False)
    db.commit()
    db.refresh(product)
    return _to_response(product)


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    image_paths = [MEDIA_DIR / img.url for img in product.images]

    # 関連テーブル(images/features/カテゴリ別サブタイプ/irelu連携等)はProductモデルの
    # cascade="all, delete-orphan"設定により自動的に削除される
    db.delete(product)
    db.commit()

    for path in image_paths:
        if path.is_file():
            path.unlink()

    return {"status": "deleted"}


@router.post("/{product_id}/images", response_model=ProductImageOut)
async def upload_product_image(product_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    current_count = db.query(ProductImage).filter(ProductImage.product_id == product_id).count()
    if current_count >= MAX_IMAGES_PER_PRODUCT:
        raise HTTPException(
            status_code=400,
            detail=f"画像は{MAX_IMAGES_PER_PRODUCT}枚までです。差し替える場合は先に既存の画像を削除してください",
        )

    ext = UPLOAD_CONTENT_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(status_code=400, detail=f"対応していない画像形式です: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="ファイルサイズが大きすぎます（上限10MB）")

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception:
        raise HTTPException(status_code=400, detail="画像として読み込めませんでした")

    # 長辺1600px・JPEG品質80%に統一して保存する（元がPNG/WebP/GIF等でもJPEG化する）。
    # スマホ撮影の4000x3000クラスの原寸をそのまま保存すると1枚数MBになり、
    # 一覧グリッド・詳細ギャラリー表示用途にはオーバースペックなため
    if image.mode != "RGB":
        image = image.convert("RGB")
    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    content = buffer.getvalue()
    ext = "jpg"

    max_sort = (
        db.query(func.max(ProductImage.sort_order))
        .filter(ProductImage.product_id == product_id)
        .scalar()
    )
    sort_order = (max_sort + 1) if max_sort is not None else 0

    product_dir = MEDIA_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{sort_order}_{uuid.uuid4().hex[:8]}.{ext}"
    (product_dir / filename).write_bytes(content)
    relative_path = f"{product_id}/{filename}"

    # source_url は "upload:" プレフィックスにして Notion/Dropbox 由来のURL(http始まり)と区別する。
    # migration/etl/load.py の sync_product_images はhttp始まりのsource_urlしか削除対象にしないため、
    # ここでアップロードした画像はNotion再同期があっても消えない
    image = ProductImage(
        product_id=product_id,
        source_url=f"upload:{uuid.uuid4().hex}",
        url=relative_path,
        sort_order=sort_order,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.delete("/{product_id}/images/{image_id}")
def delete_product_image(product_id: int, image_id: int, db: Session = Depends(get_db)):
    image = (
        db.query(ProductImage)
        .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="画像が見つかりません")

    file_path = MEDIA_DIR / image.url
    db.delete(image)
    db.commit()
    if file_path.is_file():
        file_path.unlink()
    return {"status": "deleted"}
