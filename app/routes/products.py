from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Store
from app.parser_factory import ParserFactory
from app.parser import save_product_data
from pydantic import BaseModel
from typing import List, Optional

from app.models import PriceHistory
from sqlalchemy import desc

router = APIRouter(prefix="/products", tags=["products"])


class ProductCreate(BaseModel):
    store_id: int
    product_url: str
    product_name: str = None
    target_price: float = None


class ProductResponse(BaseModel):
    id: int
    product_name: str
    product_url: str
    current_price: float
    currency: Optional[str] = "USD"
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/", response_model=ProductResponse)
def add_product(product_data: ProductCreate, db: Session = Depends(get_db)):
    """Добавляет товар на мониторинг"""

    # Проверяем, существует ли магазин
    store = db.query(Store).filter(Store.id == product_data.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Выбираем парсер через фабрику
    parser = ParserFactory.get_parser(product_data.product_url)

    # Парсим данные
    scraped_data = parser.get_product_data()

    if not scraped_data:
        raise HTTPException(status_code=400, detail="Failed to parse product data")

    # Если валюта не определена, пробуем определить по домену
    if 'currency' not in scraped_data or not scraped_data['currency']:
        scraped_data['currency'] = ParserFactory.get_region_currency(product_data.product_url)

    # Сохраняем в БД
    product = save_product_data(db, scraped_data, product_data.store_id)

    return product


@router.get("/", response_model=List[ProductResponse])
def get_products(store_id: int = None, db: Session = Depends(get_db)):
    """Получает список товаров"""

    query = db.query(Product)
    if store_id:
        query = query.filter(Product.store_id == store_id)

    return query.all()


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    scraped_at: datetime

    class Config:
        from_attributes = True


@router.get("/{product_id}/history", response_model=List[PriceHistoryResponse])
def get_price_history(product_id: int, db: Session = Depends(get_db)):
    """Получает историю цен для товара"""

    history = db.query(PriceHistory).filter(
        PriceHistory.product_id == product_id
    ).order_by(desc(PriceHistory.scraped_at)).limit(100).all()

    return history
