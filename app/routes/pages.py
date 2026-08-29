from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Store

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница (лендинг)"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Дашборд"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/history/{product_id}", response_class=HTMLResponse)
async def product_history(request: Request, product_id: int, db: Session = Depends(get_db)):
    """История цен товара"""

    # Проверяем, существует ли товар
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return templates.TemplateResponse("history.html", {
        "request": request,
        "product": product,
        "product_id": product_id
    })

@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    """Страница тарифов"""
    return templates.TemplateResponse("pricing.html", {"request": request})