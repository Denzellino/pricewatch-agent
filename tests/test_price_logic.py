from decimal import Decimal

from app.parser import check_price_changes


class FakeAlert:
    def __init__(self, product_id, chat_id, threshold_percent):
        self.product_id = product_id
        self.telegram_chat_id = chat_id
        self.threshold_percent = Decimal(str(threshold_percent))
        self.is_active = True


class FakeQuery:
    def __init__(self, alerts):
        self.alerts = alerts

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.alerts


class FakeDB:
    def __init__(self, alerts):
        self.alerts = alerts

    def query(self, model):
        return FakeQuery(self.alerts)


class FakeProduct:
    def __init__(self, product_id, name, url):
        self.id = product_id
        self.product_name = name
        self.product_url = url


def test_alert_sent_when_change_exceeds_threshold(monkeypatch):
    product = FakeProduct(1, "Test product", "https://example.com/item")
    alert = FakeAlert(1, "12345", 10)
    db = FakeDB([alert])

    sent = []
    monkeypatch.setattr(
        "app.parser.send_price_alert",
        lambda **kwargs: sent.append(kwargs),
    )

    check_price_changes(
        db=db,
        product=product,
        old_price=Decimal("100.00"),
        new_price=Decimal("85.00"),
        threshold=10.0,
    )

    assert len(sent) == 1
    assert sent[0]["old_price"] == 100.0
    assert sent[0]["new_price"] == 85.0


def test_no_alert_when_change_below_threshold(monkeypatch):
    product = FakeProduct(1, "Test product", "https://example.com/item")
    alert = FakeAlert(1, "12345", 10)
    db = FakeDB([alert])

    sent = []
    monkeypatch.setattr(
        "app.parser.send_price_alert",
        lambda **kwargs: sent.append(kwargs),
    )

    check_price_changes(
        db=db,
        product=product,
        old_price=Decimal("100.00"),
        new_price=Decimal("95.00"),
        threshold=10.0,
    )

    assert sent == []