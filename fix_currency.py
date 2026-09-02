# В терминале Python или создай скрипт fix_currency.py
from app.database import SessionLocal, init_db
from app.models import Product

init_db()
db = SessionLocal()

try:
    # Находим все товары без валюты
    products = db.query(Product).filter(Product.currency == None).all()

    for product in products:
        product.currency = 'USD'  # Или определи по домену

    db.commit()
    print(f"✅ Исправлено {len(products)} товаров")
finally:
    db.close()