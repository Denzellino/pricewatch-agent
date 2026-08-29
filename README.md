# PriceWatch Agent

AI-powered competitor price monitoring SaaS with Telegram alerts.

## Features

- Automated price scraping from competitor websites
- Real-time Telegram alerts for price changes
- Price history tracking and analytics
- Multi-store support

## Tech Stack

- Backend: FastAPI
- Database: SQLite/PostgreSQL
- Telegram Bot: python-telegram-bot
- Scheduler: APScheduler
- Deployment: Railway/Render

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` file with your API keys
4. Run: `uvicorn app.main:app --reload`

## License

MIT