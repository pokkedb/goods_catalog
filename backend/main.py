from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from database import engine, Base
import models  # noqa: F401 — registers all models with Base
from admin import ALL_ADMIN_VIEWS
from routers import products, lookups

Base.metadata.create_all(bind=engine)

app = FastAPI(title="goods_catalog 商品マスタ管理", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost|192\.168\.50\.\d+):5174",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(lookups.router)

admin = Admin(app, engine, title="goods_catalog 管理画面")
for view in ALL_ADMIN_VIEWS:
    admin.add_view(view)

MEDIA_DIR = "/pokke/databases/goods_catalog/media"
if os.path.isdir(MEDIA_DIR):
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/health")
def health():
    return {"status": "ok"}
