web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: python worker/price_monitor.py
bot: python bot/telegram_bot.py