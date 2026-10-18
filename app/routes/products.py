from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import PriceHistory, Product, User, Subscription
from app.parser_factory import ParserFactory
from app.parser import save_product_data
from app.utils.auth import get_current_active_user
from pydantic import BaseModel, field_validator


from app.models import PriceHistory
from sqlalchemy import desc

router = APIRouter(prefix="/products", tags=["products"])


class ProductCreate(BaseModel):
    product_url: str
    product_name: Optional[str] = None
    target_price: Optional[float] = None


class ProductResponse(BaseModel):
    id: int
    user_id: int
    product_name: str
    product_url: str
    current_price: Optional[float]
    currency: Optional[str]
    is_active: bool
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator("last_checked_at", mode="before")
    @classmethod
    def ensure_utc(cls, value):
        if value is None:
            return value

        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value


@router.post("/", response_model=ProductResponse)
def create_product(
        product_data: ProductCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """Добавляет товар на мониторинг"""

    # Проверяем лимит товаров
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.is_active == True
    ).first()

    max_products = subscription.max_products if subscription else 5  # Демо: 5 товаров

    current_products_count = db.query(Product).filter(
        Product.user_id == current_user.id,
        Product.is_active == True
    ).count()

    if current_products_count >= max_products:
        raise HTTPException(
            status_code=400,
            detail=f"Product limit reached. Upgrade your plan to add more products."
        )

    # Выбираем парсер
    parser = ParserFactory.get_parser(product_data.product_url)
    scraped_data = parser.get_product_data()

    if not scraped_data:
        raise HTTPException(status_code=400, detail="Failed to parse product data")

    # Определяем валюту
    if not scraped_data.get("currency"):
        scraped_data["currency"] = ParserFactory.get_region_currency(
            product_data.product_url
        )

    # Сохраняем товар
    product = save_product_data(
        db=db,
        product_data=scraped_data,
        user_id=current_user.id,
    )

    return product


@router.get("/", response_model=List[ProductResponse])
def get_products(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    """Получает список товаров пользователя"""

    products = db.query(Product).filter(
        Product.user_id == current_user.id
    ).offset(skip).limit(limit).all()

    return products


class PriceHistoryResponse(BaseModel):
    id: int
    price: float
    scraped_at: datetime

    class Config:
        from_attributes = True


@router.get(
    "/{product_id}/history",
    response_model=List[PriceHistoryResponse],
)
def get_price_history(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.user_id == current_user.id,
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(desc(PriceHistory.scraped_at))
        .limit(100)
        .all()
    )

