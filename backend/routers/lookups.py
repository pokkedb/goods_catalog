from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Brand, Maker, GoodsCategory, Refill
from schemas.lookup import LookupItem, GoodsCategoryItem
from schemas.product import PRODUCT_CATEGORIES, FEATURE_GROUP_LABELS

router = APIRouter(tags=["lookups"])


@router.get("/brands", response_model=list[LookupItem])
def list_brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.name).all()


@router.get("/makers", response_model=list[LookupItem])
def list_makers(db: Session = Depends(get_db)):
    return db.query(Maker).order_by(Maker.name).all()


@router.get("/goods-categories", response_model=list[GoodsCategoryItem])
def list_goods_categories(db: Session = Depends(get_db)):
    return db.query(GoodsCategory).order_by(GoodsCategory.name).all()


@router.get("/meta/product-categories")
def get_product_categories():
    return PRODUCT_CATEGORIES


@router.get("/meta/feature-groups")
def get_feature_groups():
    return FEATURE_GROUP_LABELS


@router.get("/meta/refill-pocket-count-labels")
def get_refill_pocket_count_labels(db: Session = Depends(get_db)):
    """既存の「リフィルポケット数」を候補として返す（表記ゆれが大きく自由入力も許すためselect+自由入力にする）"""
    rows = (
        db.query(Refill.pocket_count_label)
        .filter(Refill.pocket_count_label.isnot(None))
        .distinct()
        .order_by(Refill.pocket_count_label)
        .all()
    )
    return [r[0] for r in rows]


@router.get("/meta/refill-standards")
def get_refill_standards(db: Session = Depends(get_db)):
    rows = (
        db.query(Refill.refill_standard)
        .filter(Refill.refill_standard.isnot(None))
        .distinct()
        .order_by(Refill.refill_standard)
        .all()
    )
    return [r[0] for r in rows]
