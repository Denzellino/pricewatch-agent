from app.parser import GenericPriceParser

# Тестовый URL (замени на реальный товар)
test_url = "https://avs.by/product/vvg-p-nga-315-n660vtu-rb-428"

parser = GenericPriceParser(test_url)
result = parser.get_product_data()

if result:
    print(f"✅ Товар: {result['name']}")
    print(f"💰 Цена: {result['price']}")
    print(f"🔗 URL: {result['url']}")
else:
    print("❌ Не удалось спарсить данные")