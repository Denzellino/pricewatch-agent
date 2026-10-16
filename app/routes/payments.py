from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Subscription, User
from app.utils.auth import get_current_active_user
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
    plan: str = "basic"


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout_session(
    request_data: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
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
    existing_subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.is_active.is_(True),
        )
        .first()
    )

    if existing_subscription:
        raise HTTPException(status_code=400, detail="Active subscription already exists")

    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

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
                            "description": f"Up to {plan['max_products']} products",
                        },
                        "unit_amount": plan["price"],
                        "recurring": {
                            "interval": "month",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/payments/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/payments/cancel",
            metadata={
                "user_id": str(current_user.id),
                "plan": request_data.plan
            }
        )

        return CheckoutResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )


    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail="Stripe request failed") from exc


@router.get("/success")
def payment_success(session_id: str):
    return {
        "status": "received",
        "message": "Payment is being processed. Subscription will activate automatically.",
    }


@router.get("/cancel")
def payment_cancel():
    """Обработка отмены оплаты"""
    return {"status": "cancelled", "message": "Payment was cancelled"}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        existing = db.query(Subscription).filter(
            Subscription.stripe_checkout_session_id == session["id"]
        ).first()

        if existing:
            return {"status": "success", "message": "Already processed"}

        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")

        plans = {
            "basic": 50,
            "pro": 200,
            "enterprise": 1000,
        }

        if not user_id or plan not in plans:
            return {"status": "ignored", "message": "Invalid metadata"}

        subscription = Subscription(
            user_id=int(user_id),
            stripe_checkout_session_id=session["id"],
            stripe_customer_id=session.get("customer"),
            stripe_subscription_id=session.get("subscription"),
            plan_name=plan,
            max_products=plans[plan],
            is_active=True,
        )

        db.add(subscription)
        db.commit()

        print(
            f"✅ Stripe subscription created: "
            f"user_id={user_id}, plan={plan}, session={session['id']}"
        )

    elif event["type"] == "customer.subscription.deleted":
        stripe_subscription_id = event["data"]["object"]["id"]

        db_subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()

        if db_subscription:
            db_subscription.is_active = False
            db.commit()

            print(
                f"⛔ Stripe subscription deactivated: "
                f"{stripe_subscription_id}"
            )

    return {"status": "success"}


@router.get("/subscription")
def get_user_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.is_active.is_(True),
        )
        .first()
    )

    if not subscription:
        return {"active": False}

    return {
        "active": True,
        "plan": subscription.plan_name,
        "max_products": subscription.max_products,
        "current_period_end": subscription.current_period_end,
    }