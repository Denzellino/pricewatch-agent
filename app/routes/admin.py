from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.models import Subscription
from app.utils.auth import get_current_superuser
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/admin", tags=["admin"])


class UserAdminResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("/users", response_model=List[UserAdminResponse])
def get_all_users(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_superuser)
):
    """Получить всех пользователей (только админ)"""

    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.patch("/users/{user_id}/toggle-superuser")
def toggle_superuser(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_superuser)
):
    """Выдать/снять права админа (только админ)"""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify yourself")

    user.is_superuser = not user.is_superuser
    db.commit()

    return {"message": f"User {user.email} is now {'admin' if user.is_superuser else 'user'}"}


@router.patch("/users/{user_id}/toggle-active")
def toggle_active(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_superuser)
):
    """Активировать/деактивировать пользователя (только админ)"""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.commit()

    return {"message": f"User {user.email} is now {'active' if user.is_active else 'inactive'}"}


@router.get("/stats")
def get_stats(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_superuser)
):
    """Статистика платформы (только админ)"""

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_products = db.query(Product).count()
    paid_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_products": total_products,
        "paid_subscriptions": paid_subscriptions
    }