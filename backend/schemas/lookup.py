from pydantic import BaseModel


class LookupItem(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class GoodsCategoryItem(BaseModel):
    id: int
    name: str
    width_mm: float | None = None
    height_mm: float | None = None

    model_config = {"from_attributes": True}
