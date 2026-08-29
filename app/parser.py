import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
import re

from sqlalchemy.orm import Session
from app.models import Product, PriceHistory, Alert
from datetime import datetime

import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def send_price_alert(chat_id: str, product_name: str, old_price: float, new_price: float, product_url: str):
    """Отправляет уведомление об изменении цены"""

    change_percent = ((new_price - old_price) / old_price) * 100
    emoji = "📈" if change_percent > 0 else "📉"
    direction = "выросла" if change_percent > 0 else "упала"

    message = (
        f"{emoji} **Изменение цены!**\n\n"
        f"📦 **Товар:** {product_name[:100]}\n"
        f"💰 **Старая цена:** {old_price:.2f}\n"
        f"💰 **Новая цена:** {new_price:.2f}\n"
        f"📊 **Изменение:** {change_percent:+.1f}% ({direction})\n\n"
        f"🔗 [Открыть товар]({product_url})"
    )

    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="Markdown"
    )
    await bot.shutdown()


def check_price_changes(db: Session, product: Product, new_price: float, threshold: float = 10.0):
    """Проверяет изменение цены и отправляет уведомления"""

    old_price = product.current_price

    if isinstance(new_price, Decimal):
        new_price_raw = new_price
    else:
        # лучше через строку, чтобы избежать проблем float -> Decimal
        new_price_raw = Decimal(str(new_price))

    if not old_price:
        return

    change_percent = abs((new_price_raw - old_price) / old_price) * 100

    if change_percent >= threshold:
        # Находим все активные алерты для этого товара
        alerts = db.query(Alert).filter(
            Alert.product_id == product.id,
            Alert.is_active == True
        ).all()

        # Отправляем уведомления
        for alert in alerts:
            try:
                asyncio.run(send_price_alert(
                    chat_id=alert.telegram_chat_id,
                    product_name=product.product_name,
                    old_price=old_price,
                    new_price=new_price,
                    product_url=product.product_url
                ))
                print(f"✅ Alert sent to {alert.telegram_chat_id}")
            except Exception as e:
                print(f"❌ Failed to send alert: {e}")


def save_product_data(db: Session, product_data: Dict[str, Any], store_id: int) -> Product:
    """Сохраняет или обновляет товар в БД"""

    # Ищем существующий товар по URL
    product = db.query(Product).filter(
        Product.product_url == product_data['url'],
        Product.store_id == store_id
    ).first()

    old_price = product.current_price if product else None

    if not product:
        # Создаём новый товар
        product = Product(
            store_id=store_id,
            product_name=product_data['name'],
            product_url=product_data['url'],
            current_price=product_data['price']
        )
        db.add(product)
    else:
        # Обновляем цену
        product.current_price = product_data['price']
        product.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(product)

    # Добавляем запись в историю цен
    price_history = PriceHistory(
        product_id=product.id,
        price=product_data['price']
    )
    db.add(price_history)
    db.commit()

    # Проверяем изменение цены
    if old_price:
        check_price_changes(db, product, product_data['price'])

    return product


class PriceParser:
    """Базовый класс для парсинга цен"""

    def __init__(self, url: str):
        self.url = url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_page(self) -> Optional[str]:
        """Получает HTML страницы"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {self.url}: {e}")
            return None

    def parse_price(self, html: str) -> Optional[float]:
        """Извлекает цену из HTML (переопределяется в наследниках)"""
        raise NotImplementedError

    def parse_product_name(self, html: str) -> Optional[str]:
        """Извлекает название товара (переопределяется в наследниках)"""
        raise NotImplementedError

    def get_product_data(self) -> Optional[Dict[str, Any]]:
        """Основной метод: получает страницу и парсит данные"""
        html = self.fetch_page()
        if not html:
            return None

        price = self.parse_price(html)
        name = self.parse_product_name(html)

        if price and name:
            return {
                "name": name,
                "price": price,
                "url": self.url
            }
        return None


class GenericPriceParser(PriceParser):
    """Универсальный парсер для большинства сайтов"""

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, 'html.parser')

        # Популярные селекторы для цен
        price_selectors = [
            '.price', '.product-price', '.ourprice', '.sale-price',
            '[itemprop="price"]', '.price-current', '.product-price-value',
            '.special-price', '.regular-price'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                price = self._clean_price(price_text)
                if price:
                    return price

        # Если не нашли по селекторам, ищем по паттерну
        price_pattern = r'\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        matches = re.findall(price_pattern, html)
        if matches:
            return self._clean_price(matches[0])

        return None

    def parse_product_name(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')

        # Популярные селекторы для названий
        name_selectors = [
            'h1', '.product-name', '.product-title', '.product-heading',
            '[itemprop="name"]', '.product-title-main'
        ]

        for selector in name_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:200]  # Ограничим длину

        return "Unknown Product"

    def _clean_price(self, price_text: str) -> Optional[float]:
        """Очищает строку цены и конвертирует в float"""
        if not price_text:
            return None

        # Удаляем всё кроме цифр, точек и запятых
        cleaned = re.sub(r'[^\d.,]', '', price_text)

        # Обрабатываем запятую как разделитель копеек
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')

        try:
            return float(cleaned)
        except ValueError:
            return None

