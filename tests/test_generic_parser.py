from app.parser import GenericPriceParser


def test_parses_price_from_json_ld():
    html = """
    <html>
      <body>
        <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Тестовый товар",
          "offers": {
            "price": "12.50",
            "priceCurrency": "BYN"
          }
        }
        </script>
        <span class="price">99.99</span>
      </body>
    </html>
    """

    parser = GenericPriceParser("https://example.com/product")

    assert parser.parse_price(html) == 12.50
    assert parser.parse_currency(html) == "BYN"


def test_parses_price_from_itemprop():
    html = """
    <html>
      <body>
        <span itemprop="price" content="18.90">18,90</span>
        <span itemprop="priceCurrency" content="BYN">BYN</span>
      </body>
    </html>
    """

    parser = GenericPriceParser("https://example.com/product")

    assert parser.parse_price(html) == 18.90
    assert parser.parse_currency(html) == "BYN"


def test_parses_price_from_css_selector():
    html = """
    <html>
      <body>
        <div class="price-current">7,35 BYN</div>
      </body>
    </html>
    """

    parser = GenericPriceParser("https://example.com/product")

    assert parser.parse_price(html) == 7.35