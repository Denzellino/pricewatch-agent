from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/profile", tags=["profile"])


class TelegramBindRequest(BaseModel):
    telegram_chat_id: str


@router.post("/telegram")
def bind_telegram(
    data: TelegramBindRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chat_id = data.telegram_chat_id.strip()

    if not chat_id.isdigit() and not chat_id.startswith("-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram chat_id",
        )

    existing_user = db.query(User).filter(
        User.telegram_chat_id == chat_id
    ).first()

    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=409,
            detail="This Telegram chat is already linked to another account",
        )

    current_user.telegram_chat_id = chat_id
    db.commit()

    return {
        "status": "success",
        "telegram_chat_id": chat_id,
    }


@router.delete("/telegram")
def unbind_telegram(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    current_user.telegram_chat_id = None
    db.commit()

    return {"status": "success", "telegram_chat_id": None}