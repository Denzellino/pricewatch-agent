import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal, init_db
from app.models import Base, User  # ← Импортируем напрямую из app.models
from app.utils.auth import get_password_hash

# Инициализируем БД
init_db()

# Создаём сессию
db = SessionLocal()

try:
    # Проверяем, есть ли уже админ
    existing_admin = db.query(User).filter(User.email == "admin@pricewatch.com").first()

    if existing_admin:
        print("⚠️ Admin already exists!")
        print(f"Email: {existing_admin.email}")
    else:
        # Создаём админа
        admin = User(
            email="admin@pricewatch.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            is_superuser=True,
            is_active=True,
            is_verified=True
        )

        db.add(admin)
        db.commit()

        print("✅ Admin created!")
        print("Email: admin@pricewatch.com")
        print("Password: admin123")

finally:
    db.close()