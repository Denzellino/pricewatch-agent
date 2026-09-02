from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import re
from app.parser import GenericPriceParser


class OzonPriceParser(GenericPriceParser):
    """Парсер для Ozon.ru (Россия)"""

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, 'html.parser')

        # Селекторы для Ozon
        price_selectors = [
            '[data-testid="price-current"]', '.price-current',
            '[data-price-value]', '.product-price'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                # Ищем число: 1 234.56 или 1234,56
                match = re.search(r'(\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d{2})?)', price_text)
                if match:
                    price_str = match.group(1).replace(' ', '').replace(',', '.')
                    try:
                        return float(price_str)
                    except ValueError:
                        pass

        return None

    def parse_currency(self, html: str) -> str:
        return 'RUB'


class WBPriceParser(GenericPriceParser):
    """Парсер для Wildberries.ru (Россия)"""

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, 'html.parser')

        # Селекторы для WB
        price_selectors = [
            '.price-block__sale-price', '.price-block__price',
            '[data-price]', '.product-price'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                match = re.search(r'(\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d{2})?)', price_text)
                if match:
                    price_str = match.group(1).replace(' ', '').replace(',', '.')
                    try:
                        return float(price_str)
                    except ValueError:
                        pass

        return None

    def parse_currency(self, html: str) -> str:
        return 'RUB'


class AliExpressPriceParser(GenericPriceParser):
    """Парсер для AliExpress (международный)"""

    def parse_price(self, html: str) -> Optional[float]:
        soup = BeautifulSoup(html, 'html.parser')

        # Селекторы для AliExpress
        price_selectors = [
            '.product-price-value', '[data-testid="main-price"]',
            '.current-price', '.sale-price'
        ]

        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                # AliExpress использует $ или US $
                match = re.search(r'[\$€£]?\s*(\d+[.,]\d{2})', price_text)
                if match:
                    price_str = match.group(1).replace(',', '.')
                    try:
                        return float(price_str)
                    except ValueError:
                        pass

        return None

    def parse_currency(self, html: str) -> str:
        # Определяем валюту по символу
        if '$' in html:
            return 'USD'
        elif '€' in html:
            return 'EUR'
        elif '£' in html:
            return 'GBP'
        return 'USD'

#Доделать (Добавь другие парсеры по аналогии...)