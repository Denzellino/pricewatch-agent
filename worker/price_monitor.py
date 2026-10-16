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
from app.parser import save_product_data
from app.parser_factory import ParserFactory
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

                parser = ParserFactory.get_parser(product.product_url)
                scraped_data = parser.get_product_data()

                if scraped_data:
                    print(
                        f"✅ New price: {scraped_data['price']} "
                        f"{scraped_data.get('currency', '')}"
                    )

                    save_product_data(
                        db=db,
                        product_data=scraped_data,
                        user_id=product.user_id,
                    )
                else:
                    print(f"⚠️ Failed to parse {product.product_url}")

                time.sleep(2)

            except Exception as e:
                print(f"❌ Error parsing {product.product_url}: {e}")
                continue

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