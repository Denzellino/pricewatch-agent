import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv

from app.database import SessionLocal
from app.models import Alert, Product, User

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я PriceWatch Bot.\n\n"
        "Я буду присылать уведомления об изменении цен на товары.\n\n"
        "Команды:\n"
        "/start - Начать работу\n"
        "/help - Помощь\n"
        "/status - Статус мониторинга"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📚 Помощь:\n\n"
        "1. Добавь товар на мониторинг через веб-интерфейс\n"
        "2. Я буду присылать уведомления, если цена изменится более чем на 10%\n"
        "3. Используй /status, чтобы проверить статус\n\n"
        "Вопросы? Пиши @yourusername"
    )


async def bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /bind <product_id>\n\nПример: /bind 1"
        )
        return

    try:
        product_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Пример: /bind 1")
        return

    chat_id = str(update.message.chat_id)
    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.telegram_chat_id == chat_id
        ).first()

        if not user:
            await update.message.reply_text(
                "❌ Сначала привяжи аккаунт.\n"
                "В веб-кабинете укажи этот Telegram chat_id:\n"
                f"`{chat_id}`",
                parse_mode="Markdown",
            )
            return

        product = db.query(Product).filter(
            Product.id == product_id,
            Product.user_id == user.id,
        ).first()

        if not product:
            await update.message.reply_text(
                f"❌ Товар с ID {product_id} не найден среди твоих товаров."
            )
            return

        existing_alert = db.query(Alert).filter(
            Alert.product_id == product.id,
            Alert.telegram_chat_id == chat_id,
        ).first()

        if existing_alert:
            await update.message.reply_text(
                f"✅ Ты уже подписан на:\n{product.product_name[:100]}"
            )
            return

        alert = Alert(
            product_id=product.id,
            telegram_chat_id=chat_id,
            threshold_percent=10.0,
        )
        db.add(alert)
        db.commit()

        await update.message.reply_text(
            f"✅ Подписка оформлена!\n\n"
            f"📦 {product.product_name[:100]}\n"
            f"💰 Текущая цена: {product.current_price}\n"
            f"🔔 Порог: 10%"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        db.close()


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    chat_id = str(update.message.chat_id)

    db = SessionLocal()

    try:
        alerts = db.query(Alert).filter(
            Alert.telegram_chat_id == chat_id,
            Alert.is_active == True
        ).all()

        if not alerts:
            await update.message.reply_text(
                "🔔 У вас нет активных подписок\n\n"
                "Используйте /bind <product_id> для подписки"
            )
        else:
            message = "🔔 Ваши подписки:\n\n"
            for alert in alerts:
                product = db.query(Product).filter(Product.id == alert.product_id).first()
                if product:
                    message += f"📦 {product.product_name[:50]}\n"
                    message += f"💰 Цена: {product.current_price}\n"
                    message += f"🔗 ID: {product.id}\n\n"

            await update.message.reply_text(message)

    finally:
        db.close()


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных команд"""
    await update.message.reply_text("Не знаю такую команду 😕\nИспользуй /help")


def run_bot():
    """Запускает бота"""
    app = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("bind", bind))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    # Запускаем
    print("🤖 Telegram bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()