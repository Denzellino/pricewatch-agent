from app.database import SessionLocal
from app.models import User
from app.utils.auth import get_password_hash

db = SessionLocal()

try:
    user = db.query(User).filter(User.id == 3).first()

    if not user:
        print("User with id=3 not found")
    else:
        user.hashed_password = get_password_hash("newpassword123")
        db.commit()
        print(f"Password updated for {user.email}")

finally:
    db.close()