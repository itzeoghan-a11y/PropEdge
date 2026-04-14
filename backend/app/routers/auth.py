from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    StripeCheckoutOut,
    TokenOut,
    UserOut,
    UserRegister,
    UserUpdate,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

stripe.api_key = settings.stripe_secret_key


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()

    # Create Stripe customer
    if settings.stripe_secret_key:
        try:
            customer = stripe.Customer.create(email=payload.email)
            user.stripe_customer_id = customer.id
        except Exception:
            pass   # non-fatal

    return user


@router.post("/token", response_model=TokenOut)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    return current_user


@router.post("/checkout/{tier}", response_model=StripeCheckoutOut)
async def create_checkout(
    tier: str,
    current_user: User = Depends(get_current_user),
):
    if tier not in ("pro", "elite"):
        raise HTTPException(status_code=400, detail="Invalid tier")
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Payments not configured")

    price_id = settings.stripe_price_pro if tier == "pro" else settings.stripe_price_elite

    session = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:3000/settings?upgraded=1",
        cancel_url="http://localhost:3000/pricing",
        metadata={"user_id": str(current_user.id), "tier": tier},
    )
    return StripeCheckoutOut(checkout_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        tier    = session["metadata"]["tier"]
        sub_id  = session.get("subscription")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.tier = tier
            user.stripe_subscription_id = sub_id
            user.subscription_status = "active"

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        result = await db.execute(
            select(User).where(User.stripe_subscription_id == sub["id"])
        )
        user = result.scalar_one_or_none()
        if user:
            user.tier = "free"
            user.subscription_status = "cancelled"

    return {"status": "ok"}
