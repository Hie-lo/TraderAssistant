from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, check_heavy_limit
from app.core.security import AuthenticatedUser
from app.repositories.payment_repo import PaymentRepository
from app.repositories.user_repo import UserRepository
from app.services.subscription_service import SubscriptionService

router = APIRouter(tags=["Payments & VIP"])


@router.get("/vip/plans")
async def get_vip_plans_and_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns VIP plans, admin bank card info, user's active subscription, and receipt history."""
    user_repo = UserRepository(db)
    pay_repo = PaymentRepository(db)
    db_user = await user_repo.get_by_id(current_user.id)
    effective_role = await user_repo.resolve_effective_role(db_user)
    payments = await pay_repo.list_by_user(current_user.id, limit=15)

    return {
        **SubscriptionService.get_vip_public_config(),
        "role": "ADMIN" if current_user.role == "ADMIN" else effective_role,
        "subscriptionEndDate": (
            db_user.subscription_end_date.isoformat()
            if db_user and db_user.subscription_end_date
            else None
        ),
        "payments": [SubscriptionService.serialize_payment(p, db_user) for p in payments],
    }


@router.post("/payments", status_code=201)
async def submit_vip_payment(
    plan_duration: int = Form(...),
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(check_heavy_limit),
    db: AsyncSession = Depends(get_db)
):
    """Submits a VIP payment receipt image (1, 3, or 6 months) for admin review."""
    file_bytes = await file.read()
    payment = await SubscriptionService.submit_payment(
        session=db,
        user_id=current_user.id,
        plan_duration=plan_duration,
        file_bytes=file_bytes,
    )
    return {
        "success": True,
        "message": "فیش واریزی شما با موفقیت ثبت شد و در انتظار تأیید ادمین است.",
        "payment": SubscriptionService.serialize_payment(payment),
    }
