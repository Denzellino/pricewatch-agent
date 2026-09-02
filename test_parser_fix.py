import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.parser import GenericPriceParser

# Тестовый URL (замени на свой)
test_url = "https://example.com/product/123"

parser = GenericPriceParser(test_url)
result = parser.get_product_data()

if result:
    print(f"✅ Товар: {result['name']}")
    print(f"💰 Цена: {result['price']}")
    print(f"💱 Валюта: {result['currency']}")
    print(f"🔗 URL: {result['url']}")
else:
    print("❌ Не удалось спарсить данные")