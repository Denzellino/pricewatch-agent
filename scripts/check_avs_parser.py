import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.parser_factory import ParserFactory
from app.database import SessionLocal, init_db
from app.models import Product

# Тестовый URL
test_url = "https://avs.by/product/vvg-p-nga-315-n660vtu-rb-428"

# Тестируем парсер
parser = ParserFactory.get_parser(test_url)
result = parser.get_product_data()

print("🔍 Результат парсинга:")
if result:
    print(f"✅ Товар: {result['name']}")
    print(f"💰 Цена: {result['price']}")
    print(f"💱 Валюта: {result['currency']}")
    print(f"🔗 URL: {result['url']}")
else:
    print("❌ Не удалось спарсить данные")

# Проверяем, что в БД
print("\n🗄️ Товары в БД:")
init_db()
db = SessionLocal()

try:
    products = db.query(Product).filter(Product.product_url == test_url).all()

    if products:
        for product in products:
            print(f"ID: {product.id}")
            print(f"Название: {product.product_name}")
            print(f"Цена: {product.current_price}")
            print(f"Валюта: {product.currency}")  # ← Проверяем это поле
    else:
        print("Товар не найден в БД")
finally:
    db.close()