# 🔍 PriceWatch Agent

**Версия:** 0.1.0

Автоматическая система мониторинга цен конкурентов для e-commerce с уведомлениями в Telegram.

## 🚀 Возможности

- ✅ Авторизация и регистрация (JWT)
- ✅ Управление товарами через дашборд
- ✅ Автоматический парсинг цен
- ✅ Уведомления в Telegram
- ✅ 4 тарифных плана (Demo, Basic, Pro, Enterprise)
- ✅ REST API

## 🛠 Технологии

- **Backend:** Python 3.13, FastAPI, SQLAlchemy, Pydantic
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Security:** JWT, bcrypt

## 📦 Установка

```bash
# Клонирование
git clone [https://github.com/твой-username/pricewatch-agent.git](https://github.com/твой-username/pricewatch-agent.git)
cd pricewatch-agent

# Установка зависимостей
pip install -r requirements.txt

# Запуск
uvicorn app.main:app --reload
```

## 🔑 Первый вход

- **Email:** admin@pricewatch.com
- **Пароль:** admin123

## 📚 Документация API

После запуска открой: http://127.0.0.1:8000/docs

## 📄 Лицензия

MIT