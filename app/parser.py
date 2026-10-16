import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

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


def check_price_changes(
    db: Session,
    product: Product,
    old_price,
    new_price,
    threshold: float = 10.0,
):
    if old_price is None or new_price is None:
        return

    old_price = Decimal(str(old_price))
    new_price = Decimal(str(new_price))

    if old_price == 0:
        return

    change_percent = abs((new_price - old_price) / old_price) * Decimal("100")

    alerts = db.query(Alert).filter(
        Alert.product_id == product.id,
        Alert.is_active.is_(True),
    ).all()

    for alert in alerts:
        alert_threshold = Decimal(
            str(alert.threshold_percent or threshold)
        )

        if change_percent < alert_threshold:
            continue

        try:
            asyncio.run(
                send_price_alert(
                    chat_id=alert.telegram_chat_id,
                    product_name=product.product_name,
                    old_price=float(old_price),
                    new_price=float(new_price),
                    product_url=product.product_url,
                )
            )
            print(f"✅ Alert sent to {alert.telegram_chat_id}")
        except Exception as e:
            print(f"❌ Failed to send alert: {e}")


def save_product_data(
    db: Session,
    product_data: Dict[str, Any],
    user_id: int,
) -> Product:
    url = product_data["url"]
    new_price = Decimal(str(product_data["price"]))

    product = db.query(Product).filter(
        Product.product_url == url,
        Product.user_id == user_id,
    ).first()

    old_price = product.current_price if product else None

    if product is None:
        product = Product(
            user_id=user_id,
            product_name=product_data["name"],
            product_url=url,
            current_price=new_price,
            currency=product_data.get("currency", "USD"),
        )
        db.add(product)
        db.flush()
    else:
        product.product_name = product_data["name"]
        product.current_price = new_price
        product.currency = product_data.get(
            "currency",
            product.currency or "USD",
        )
        product.updated_at = datetime.utcnow()

    price_history = PriceHistory(
        product_id=product.id,
        price=new_price,
    )
    db.add(price_history)
    db.commit()
    db.refresh(product)

    if old_price is not None:
        check_price_changes(
            db=db,
            product=product,
            old_price=old_price,
            new_price=new_price,
        )

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
        currency = self.parse_currency(html)

        if price is not None and name:
            return {
                "name": name,
                "price": price,
                "currency": currency,
                "url": self.url
            }
        return None


class GenericPriceParser(PriceParser):
    """Универсальный парсер для большинства сайтов"""

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, 'html.parser')

        # Приоритетные селекторы для текущей цены
        priority_selectors = [
            '.price-current', '.ourprice', '.sale-price', '.special-price',
            '[itemprop="price"]', '.price-final', '.actual-price'
        ]

        # Сначала ищем по приоритетным селекторам
        for selector in priority_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                price = self._clean_price(price_text)
                if price:
                    return price

        # Затем ищем по обычным селекторам
        price_selectors = [
            '.price', '.product-price', '.price-value', '.product-price-value',
            '.regular-price', '.product-price-new'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                price = self._clean_price(price_text)
                if price:
                    return price

        # Если не нашли по селекторам, ищем по паттерну
        # Паттерн для цен: 2.54, 2,54, $2.54, 2.54 BYN
        price_pattern = r'(\d+[.,]\d{2})\s*(?:BYN|RUB|USD|EUR|₽|\$|€)?'
        matches = re.findall(price_pattern, html)

        if matches:
            price_str = matches[0].replace(',', '.')
            try:
                return float(price_str)
            except ValueError:
                pass

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

        # Находим все числа в строке
        import re

        # Паттерн для поиска цен: 2.54, 2,54, $2.54, 2.54 BYN и т.д.
        price_pattern = r'(\d+[.,]\d{2})'
        matches = re.findall(price_pattern, price_text)

        if matches:
            # Берём первое найденное число
            price_str = matches[0]
            # Заменяем запятую на точку
            price_str = price_str.replace(',', '.')

            try:
                return float(price_str)
            except ValueError:
                return None

        # Если не нашли десятичное число, ищем целые
        price_pattern = r'(\d+)'
        matches = re.findall(price_pattern, price_text)

        if matches:
            try:
                return float(matches[0])
            except ValueError:
                return None

        return None


    def parse_currency(self, html: str) -> str:
        """Определяет валюту из HTML"""

        soup = BeautifulSoup(html, 'html.parser')

        # Популярные селекторы для валюты
        currency_element = soup.select_one(
            '[itemprop="priceCurrency"]'
        )

        if currency_element:
            currency = (
                    currency_element.get("content")
                    or currency_element.get_text(strip=True)
            ).upper()

            if currency in {"BYN", "RUB", "USD", "EUR", "KZT", "UAH"}:
                return currency

        # Ищем в атрибутах
        price_elements = soup.select('[itemprop="price"]')
        for element in price_elements:
            currency = element.get('content', '').upper()
            if currency in ['BYN', 'RUB', 'USD', 'EUR', 'KZT', 'UAH']:
                return currency

        # Ищем по паттернам в тексте
        currency_patterns = {
            'BYN': r'\bBYN\b|\bбел\.\s?руб\.\b|\bruble\b',
            'RUB': r'\bRUB\b|\bруб\.\b|\b₽\b',
            'USD': r'\bUSD\b|\$\b',
            'EUR': r'\bEUR\b|\b€\b',
            'KZT': r'\bKZT\b|\b₸\b',
            'UAH': r'\bUAH\b|\b₴\b'
        }

        for currency, pattern in currency_patterns.items():
            if re.search(pattern, html, re.IGNORECASE):
                return currency

        # По умолчанию
        return 'USD'


class AVSPriceParser(GenericPriceParser):
    """Специальный парсер для avs.by (Беларусь)"""

    def parse_price(self, html: str) -> Optional[float]:
        import re

        # Ищем цену рядом с "руб" или "BYN"
        price_pattern = r'(\d+[.,]\d{2})\s*(?:руб|BYN|бел\.\s*руб)'
        matches = re.findall(price_pattern, html, re.IGNORECASE)

        if matches:
            # Берём первое найденное совпадение
            price_str = matches[0].replace(',', '.')
            try:
                return float(price_str)
            except ValueError:
                pass

        # Если не нашли, пробуем другие паттерны
        soup = BeautifulSoup(html, 'html.parser')

        # Специфичные селекторы для avs.by
        price_selectors = [
            '.product-price', '.price-value', '[data-price]',
            '.cost', '.price-current', '.price-main', '.price-final'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                # Ищем число в формате 2,48 или 2.48
                match = re.search(r'(\d+[.,]\d{2})', price_text)
                if match:
                    price_str = match.group(1).replace(',', '.')
                    try:
                        return float(price_str)
                    except ValueError:
                        pass

        return None

    def parse_currency(self, html: str) -> str:
        import re

        # Проверяем, есть ли "BYN" или "бел. руб." на странице
        if re.search(r'\bBYN\b|\bбел\.\s*руб\.\b', html, re.IGNORECASE):
            return 'BYN'

        # Если есть "руб" но нет "BYN", всё равно возвращаем BYN (для avs.by)
        if re.search(r'\bруб\b', html, re.IGNORECASE):
            return 'BYN'

        return 'USD'