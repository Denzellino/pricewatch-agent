import logging
import os
import sys
import time
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal
from app.models import Product
from app.parser import save_product_data
from app.parser_factory import ParserFactory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("price_monitor")

CHECK_INTERVAL_MINUTES = int(os.getenv("PRICE_CHECK_INTERVAL_MINUTES", "30"))
REQUEST_DELAY_SECONDS = float(os.getenv("PRICE_CHECK_DELAY_SECONDS", "2"))


def process_product(product_id: int) -> bool:
    """Парсит и сохраняет цену одного товара в отдельной DB-сессии."""

    db = SessionLocal()

    try:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.is_active.is_(True),
        ).first()

        if not product:
            logger.warning("Product %s not found or inactive", product_id)
            return False

        parser = ParserFactory.get_parser(product.product_url)
        scraped_data = parser.get_product_data()

        if not scraped_data:
            logger.warning(
                "Failed to parse product_id=%s url=%s",
                product.id,
                product.product_url,
            )
            return False

        old_price = product.current_price

        save_product_data(
            db=db,
            product_data=scraped_data,
            user_id=product.user_id,
            product_id=product.id,
        )

        logger.info(
            "Product %s updated: %s -> %s %s",
            product.id,
            old_price,
            scraped_data["price"],
            scraped_data.get("currency", ""),
        )

        return True

    except Exception:
        logger.exception("Error processing product_id=%s", product_id)
        return False

    finally:
        db.close()


def monitor_prices():
    """Проверяет все активные товары."""

    logger.info("Starting price monitoring")

    db = SessionLocal()

    try:
        product_ids = [
            row[0]
            for row in db.query(Product.id).filter(
                Product.is_active.is_(True)
            ).all()
        ]
    finally:
        db.close()

    logger.info("Found %s active products", len(product_ids))

    updated = 0
    failed = 0

    for product_id in product_ids:
        if process_product(product_id):
            updated += 1
        else:
            failed += 1

        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info(
        "Price monitoring finished: updated=%s, failed=%s",
        updated,
        failed,
    )


def run_scheduler():
    scheduler = BlockingScheduler()

    scheduler.add_job(
        monitor_prices,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
        id="price_monitor",
        replace_existing=True,
    )

    logger.info(
        "Price monitor scheduler started; interval=%s minutes",
        CHECK_INTERVAL_MINUTES,
    )

    monitor_prices()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Price monitor scheduler stopped")


if __name__ == "__main__":
    run_scheduler()