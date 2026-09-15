from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product
from app.models import User

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

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Страница тарифов"""
    return templates.TemplateResponse("pricing.html", {"request": request})