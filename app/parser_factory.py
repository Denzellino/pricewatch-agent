from typing import Optional, Type
from app.parser import PriceParser, GenericPriceParser


class ParserFactory:
    """Фабрика для выбора парсера в зависимости от домена/региона"""

    # Маппинг доменов к парсерам
    DOMAIN_PARSERS = {
        'avs.by': 'AVSPriceParser',
        'ozon.ru': 'OzonPriceParser',
        'wildberries.ru': 'WBPriceParser',
        'aliexpress.com': 'AliExpressPriceParser',
        'amazon.com': 'AmazonPriceParser',
        'kaspi.kz': 'KaspiPriceParser',
        'epicentr.k.ua': 'EpicentrPriceParser',
    }

    # Маппинг регионов к валютам по умолчанию
    REGION_CURRENCIES = {
        'by': 'BYN',
        'ru': 'RUB',
        'kz': 'KZT',
        'ua': 'UAH',
        'com': 'USD',
    }

    @classmethod
    def get_parser(cls, url: str) -> PriceParser:
        """Возвращает подходящий парсер для URL"""

        from urllib.parse import urlparse
        from app.parser import AVSPriceParser  # Импортируем специфичные парсеры
        from app.parsers.regional_parsers import (
            OzonPriceParser, WBPriceParser, AliExpressPriceParser
        )

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain = domain.replace('www.', '')

        # Проверяем домены
        if 'avs.by' in domain:
            return AVSPriceParser(url)
        elif 'ozon.ru' in domain:
            return OzonPriceParser(url)
        elif 'wildberries.ru' in domain:
            return WBPriceParser(url)
        elif 'aliexpress' in domain:
            return AliExpressPriceParser(url)
        # Доделать (Добавь другие...)

        # Если нет специального парсера, используем универсальный
        return GenericPriceParser(url)

    @classmethod
    def get_region_currency(cls, url: str) -> str:
        """Определяет валюту по домену"""

        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Проверяем домен
        for tld, currency in cls.REGION_CURRENCIES.items():
            if f'.{tld}' in domain or domain.endswith(tld):
                return currency

        # По умолчанию
        return 'USD'