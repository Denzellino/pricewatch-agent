from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Store
from datetime import datetime
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/stores", tags=["stores"])


class StoreCreate(BaseModel):
    user_id: int
    store_name: str


class StoreResponse(BaseModel):
    id: int
    user_id: int
    store_name: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=StoreResponse)
def create_store(store_data: StoreCreate, db: Session = Depends(get_db)):
    """Создаёт новый магазин"""

    store = Store(
        user_id=store_data.user_id,
        store_name=store_data.store_name
    )

    db.add(store)
    db.commit()
    db.refresh(store)

    return store


@router.get("/", response_model=List[StoreResponse])
def get_stores(user_id: int = None, db: Session = Depends(get_db)):
    """Получает список магазинов"""

    query = db.query(Store)
    if user_id:
        query = query.filter(Store.user_id == user_id)

    return query.all()


@router.get("/{store_id}", response_model=StoreResponse)
def get_store(store_id: int, db: Session = Depends(get_db)):
    """Получает магазин по ID"""

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    return store