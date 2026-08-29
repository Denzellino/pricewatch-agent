import sys
import os
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Теперь импорты работают
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Product
from app.parser import GenericPriceParser, save_product_data
import time
from datetime import datetime


def monitor_prices():
    """Основная функция мониторинга: парсит все активные товары"""

    print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting price monitoring...")

    db = SessionLocal()

    try:
        # Получаем все активные товары
        products = db.query(Product).filter(Product.is_active == True).all()

        print(f"📦 Found {len(products)} active products")

        for product in products:
            try:
                print(f"🔍 Parsing: {product.product_name[:50]}...")

                # Парсим URL
                parser = GenericPriceParser(product.product_url)
                scraped_data = parser.get_product_data()

                if scraped_data:
                    print(f"✅ New price: {scraped_data['price']}")

                    # Сохраняем данные (с проверкой изменений)
                    save_product_data(db, scraped_data, product.store_id)
                else:
                    print(f"⚠️ Failed to parse {product.product_url}")

                # Небольшая задержка, чтобы не блокировали
                time.sleep(2)

            except Exception as e:
                print(f"❌ Error parsing {product.product_url}: {e}")
                continue

        print(f"✅ Price monitoring completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    finally:
        db.close()


def run_scheduler():
    """Запускает планировщик задач"""

    scheduler = BlockingScheduler()

    # Добавляем задачу: запускать каждые 30 минут
    scheduler.add_job(
        monitor_prices,
        trigger=IntervalTrigger(minutes=30),
        id='price_monitor',
        replace_existing=True
    )

    print("🤖 Price monitor scheduler started...")
    print("⏰ Checking prices every 30 minutes")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Scheduler stopped")


if __name__ == "__main__":
    run_scheduler()