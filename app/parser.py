import re
import requests
import os
import asyncio
import json

from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from app.models import Product, PriceHistory, Alert
from datetime import datetime
from html import escape


from telegram import Bot
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
        f'🔗 <a href="{escape(product_url)}">Открыть товар</a>'
    )

    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="HTML"
    )
    await bot.shutdown()


def check_price_changes(
    db: Session,
    product: Product,
    old_price,
    new_price,
    threshold: float = 10.0,
):
    """Проверяет изменение цены и отправляет уведомления"""

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
    product_id: int | None = None,
) -> Product:
    url = product_data["url"]
    new_price = Decimal(str(product_data["price"]))

    product = None

    if product_id is not None:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.user_id == user_id,
        ).first()

    if product is None:
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
            last_checked_at=datetime.utcnow(),
            last_error=None,
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
        product.last_checked_at = datetime.utcnow()
        product.last_error = None
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

    def _parse_json_ld(self, soup: BeautifulSoup) -> tuple[Optional[float], Optional[str]]:
        """Ищет цену и валюту в JSON-LD."""

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except (TypeError, json.JSONDecodeError):
                continue

            candidates = data if isinstance(data, list) else [data]

            for item in candidates:
                if not isinstance(item, dict):
                    continue

                offers = item.get("offers")

                if isinstance(offers, list):
                    offers = offers[0] if offers else None

                if not isinstance(offers, dict):
                    continue

                price = offers.get("price") or offers.get("lowPrice")
                currency = offers.get("priceCurrency")

                parsed_price = self._clean_price(str(price)) if price else None

                if parsed_price:
                    return parsed_price, currency.upper() if currency else None

        return None, None

    def _parse_microdata(self, soup: BeautifulSoup) -> tuple[Optional[float], Optional[str]]:
        """Ищет цену и валюту в itemprop / meta-тегах."""

        price_el = soup.select_one('[itemprop="price"]')
        currency_el = soup.select_one('[itemprop="priceCurrency"]')

        price = None
        currency = None

        if price_el:
            price = (
                price_el.get("content")
                or price_el.get_text(strip=True)
            )

        if currency_el:
            currency = (
                currency_el.get("content")
                or currency_el.get_text(strip=True)
            )

        if not price:
            meta_price = soup.find("meta", property="product:price:amount")
            if meta_price:
                price = meta_price.get("content")

        if not currency:
            meta_currency = soup.find("meta", property="product:price:currency")
            if meta_currency:
                currency = meta_currency.get("content")

        parsed_price = self._clean_price(str(price)) if price else None

        if parsed_price:
            return parsed_price, currency.upper() if currency else None

        return None, None

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, "html.parser")

        price, _ = self._parse_json_ld(soup)
        if price:
            return price

        price, _ = self._parse_microdata(soup)
        if price:
            return price

        priority_selectors = [
            ".price-current",
            ".ourprice",
            ".sale-price",
            ".special-price",
            '[itemprop="price"]',
            ".price-final",
            ".actual-price",
        ]

        for selector in priority_selectors:
            element = soup.select_one(selector)
            if element:
                price = self._clean_price(element.get_text(strip=True))
                if price:
                    return price

        price_selectors = [
            ".price",
            ".product-price",
            ".price-value",
            ".product-price-value",
            ".regular-price",
            ".product-price-new",
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price = self._clean_price(element.get_text(strip=True))
                if price:
                    return price

        matches = re.findall(
            r"(\d+[.,]\d{2})\s*(?:BYN|RUB|USD|EUR|₽|\$|€)?",
            html,
        )

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
        soup = BeautifulSoup(html, "html.parser")

        _, currency = self._parse_json_ld(soup)

        if not currency:
            _, currency = self._parse_microdata(soup)

        if currency in {"BYN", "RUB", "USD", "EUR", "KZT", "UAH"}:
            return currency

        currency_patterns = {
            "BYN": r"\bBYN\b|\bбел\.\s?руб\.\b",
            "RUB": r"\bRUB\b|\bруб\.\b|\b₽\b",
            "USD": r"\bUSD\b|\$\b",
            "EUR": r"\bEUR\b|\b€\b",
            "KZT": r"\bKZT\b|\b₸\b",
            "UAH": r"\bUAH\b|\b₴\b",
        }

        for currency, pattern in currency_patterns.items():
            if re.search(pattern, html, re.IGNORECASE):
                return currency

        return "USD"


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