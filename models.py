from typing import List

from pydantic import BaseModel


class Product(BaseModel):
    title: str
    price: int
    link: str


class ProductList(BaseModel):
    products: List[Product]
