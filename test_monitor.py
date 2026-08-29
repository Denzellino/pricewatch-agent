import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal, init_db
from app.models import Product
from app.parser import GenericPriceParser, save_product_data

# Инициализируем БД
init_db()

db = SessionLocal()

try:
    # Получаем первый активный товар
    product = db.query(Product).filter(Product.is_active == True).first()

    if not product:
        print("❌ No active products found")
    else:
        print(f"📦 Testing: {product.product_name}")
        print(f"🔗 URL: {product.product_url}")
        print(f"💰 Current price: {product.current_price}")

        # Парсим
        parser = GenericPriceParser(product.product_url)
        scraped_data = parser.get_product_data()

        if scraped_data:
            print(f"\n✅ Scraped data:")
            print(f"   Name: {scraped_data['name']}")
            print(f"   Price: {scraped_data['price']}")

            # Сохраняем
            updated_product = save_product_data(db, scraped_data, product.store_id)
            print(f"\n✅ Product updated in database")
        else:
            print("❌ Failed to scrape product data")

finally:
    db.close()