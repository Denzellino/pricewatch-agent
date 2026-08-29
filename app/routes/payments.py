from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Subscription, Store
from pydantic import BaseModel
from typing import Optional, List
import stripe
import os
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    user_id: int
    plan: str = "basic"  # basic, pro, enterprise


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout_session(request_data: CheckoutRequest, db: Session = Depends(get_db)):
    """Создаёт Stripe Checkout сессию"""

    # Определяем цены
    plans = {
        "basic": {
            "price": 2900,  # $29 в центах
            "name": "Basic Plan",
            "max_products": 50
        },
        "pro": {
            "price": 7900,  # $79
            "name": "Pro Plan",
            "max_products": 200
        },
        "enterprise": {
            "price": 19900,  # $199
            "name": "Enterprise Plan",
            "max_products": 1000
        }
    }

    if request_data.plan not in plans:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = plans[request_data.plan]

    # Проверяем, есть ли уже активная подписка
    existing_subscription = db.query(Subscription).filter(
        Subscription.user_id == request_data.user_id,
        Subscription.is_active == True
    ).first()

    if existing_subscription:
        raise HTTPException(status_code=400, detail="Active subscription already exists")

    # Создаём Stripe Checkout сессию
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": plan["name"],
                            "description": f"Up to {plan['max_products']} products"
                        },
                        "unit_amount": plan["price"],
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",  # ← Изменили с "subscription" на "payment"
            success_url=f"{FRONTEND_URL}/payments/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/payments/cancel",
            metadata={
                "user_id": str(request_data.user_id),
                "plan": request_data.plan
            }
        )

        return CheckoutResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.get("/success")
def payment_success(session_id: str, db: Session = Depends(get_db)):
    """Обработка успешной оплаты"""

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        if session.payment_status == "paid":
            user_id = int(session.metadata["user_id"])
            plan = session.metadata["plan"]

            # Получаем план
            plans = {
                "basic": 50,
                "pro": 200,
                "enterprise": 1000
            }

            # Создаём подписку в БД
            subscription = Subscription(
                user_id=user_id,
                stripe_customer_id=session.customer,
                stripe_subscription_id=session.subscription,
                plan_name=plan,
                max_products=plans.get(plan, 50),
                is_active=True
            )

            db.add(subscription)
            db.commit()

            return {"status": "success", "message": "Payment successful!"}
        else:
            return {"status": "pending", "message": "Payment pending"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cancel")
def payment_cancel():
    """Обработка отмены оплаты"""
    return {"status": "cancelled", "message": "Payment was cancelled"}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook для обработки событий Stripe"""

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    # Обрабатываем события
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Дополнительная логика

    elif event["type"] == "customer.subscription.deleted":
        subscription_id = event["data"]["object"]["id"]
        # Деактивируем подписку в БД
        db_subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()

        if db_subscription:
            db_subscription.is_active = False
            db.commit()

    return {"status": "success"}


@router.get("/subscription/{user_id}")
def get_user_subscription(user_id: int, db: Session = Depends(get_db)):
    """Получает информацию о подписке пользователя"""

    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.is_active == True
    ).first()

    if not subscription:
        return {"active": False}

    return {
        "active": True,
        "plan": subscription.plan_name,
        "max_products": subscription.max_products,
        "current_period_end": subscription.current_period_end
    }