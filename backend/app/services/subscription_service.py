from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import BusinessValidationError, NotFoundError
from app.core.logger import logger
from app.models.payment import Payment
from app.models.user import User
from app.repositories.payment_repo import PaymentRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.user_repo import UserRepository
from app.services.chart_service import ChartService


class SubscriptionService:
    """Handles VIP subscription plans, payment receipt submission, admin approvals, and manual VIP edits."""

    VALID_PLANS = (1, 3, 6)

    @staticmethod
    def get_vip_public_config() -> Dict[str, Any]:
        prices = DynamicConfig.get("vip_prices", {"1": 290000, "3": 750000, "6": 1350000})
        return {
            "adminCardNumber": str(DynamicConfig.get("admin_card_number", "6037-9911-0000-0000")),
            "adminCardName": str(DynamicConfig.get("admin_card_name", "مدیر سیستم")),
            "vipPrices": prices,
        }

    @classmethod
    def serialize_payment(cls, p: Payment, user: Optional[User] = None) -> Dict[str, Any]:
        return {
            "id": p.id,
            "userId": p.user_id,
            "username": user.username if user else None,
            "firstName": user.first_name if user else f"User {p.user_id}",
            "planDuration": p.plan_duration,
            "receiptImageUrl": p.receipt_image_url,
            "status": p.status,
            "createdAt": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
        }

    @classmethod
    async def submit_payment(
        cls,
        session: AsyncSession,
        user_id: int,
        plan_duration: int,
        file_bytes: bytes,
    ) -> Payment:
        if plan_duration not in cls.VALID_PLANS:
            raise BusinessValidationError("مدت اشتراک انتخابی معتبر نیست (فقط ۱، ۳ یا ۶ ماهه).")
        if not file_bytes:
            raise BusinessValidationError("تصویر فیش واریزی ارسال نشده است.")

        receipt_url = await ChartService.process_receipt_upload(file_bytes)
        payment = Payment(
            user_id=user_id,
            plan_duration=plan_duration,
            receipt_image_url=receipt_url,
            status="PENDING",
        )
        saved = await PaymentRepository(session).create(payment)
        logger.info(f"User {user_id} submitted VIP payment #{saved.id} ({plan_duration}m)")
        return saved

    @classmethod
    async def approve_payment(
        cls,
        session: AsyncSession,
        admin_id: int,
        payment_id: int,
    ) -> Dict[str, Any]:
        pay_repo = PaymentRepository(session)
        user_repo = UserRepository(session)
        sys_repo = SystemRepository(session)

        payment = await pay_repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("تراکنش مورد نظر یافت نشد.")
        if payment.status != "PENDING":
            raise BusinessValidationError(f"این فیش قبلاً بررسی شده است (وضعیت: {payment.status}).")

        user = await user_repo.get_by_id(payment.user_id)
        if not user:
            raise NotFoundError("کاربر صاحب فیش یافت نشد.")

        now = datetime.now(timezone.utc)
        current_end = user.subscription_end_date
        if current_end and current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=timezone.utc)

        base_dt = current_end if (current_end and current_end > now) else now
        new_end = base_dt + timedelta(days=30 * payment.plan_duration)
        new_role = "ADMIN" if user.role == "ADMIN" else "VIP"

        payment.status = "APPROVED"
        user.role = new_role
        user.subscription_end_date = new_end
        await session.commit()
        await session.refresh(payment)
        await session.refresh(user)

        await sys_repo.add_audit_log(
            admin_id=admin_id,
            action="APPROVE_PAYMENT",
            target_id=str(payment.id),
            details={
                "user_id": user.id,
                "plan_duration": payment.plan_duration,
                "new_end_date": new_end.isoformat(),
            },
        )
        logger.info(f"Admin {admin_id} approved payment #{payment.id} for user {user.id} until {new_end.isoformat()}")
        return {"payment": cls.serialize_payment(payment, user), "subscriptionEndDate": new_end.isoformat(), "userRole": user.role}

    @classmethod
    async def reject_payment(
        cls,
        session: AsyncSession,
        admin_id: int,
        payment_id: int,
    ) -> Dict[str, Any]:
        pay_repo = PaymentRepository(session)
        sys_repo = SystemRepository(session)

        payment = await pay_repo.get_by_id(payment_id)
        if not payment:
            raise NotFoundError("تراکنش مورد نظر یافت نشد.")
        if payment.status != "PENDING":
            raise BusinessValidationError(f"این فیش قبلاً بررسی شده است (وضعیت: {payment.status}).")

        payment.status = "REJECTED"
        await session.commit()
        await session.refresh(payment)

        await sys_repo.add_audit_log(
            admin_id=admin_id,
            action="REJECT_PAYMENT",
            target_id=str(payment.id),
            details={"user_id": payment.user_id, "plan_duration": payment.plan_duration},
        )
        logger.info(f"Admin {admin_id} rejected payment #{payment.id}")
        return cls.serialize_payment(payment)

    @classmethod
    async def manual_update_vip(
        cls,
        session: AsyncSession,
        admin_id: int,
        target_user_id: int,
        action: str,
        days: Optional[int] = None,
        exact_date: Optional[str] = None,
        role: Optional[str] = None,
    ) -> User:
        user_repo = UserRepository(session)
        sys_repo = SystemRepository(session)

        user = await user_repo.get_by_id(target_user_id)
        if not user:
            raise NotFoundError(f"کاربری با شناسه {target_user_id} یافت نشد.")

        now = datetime.now(timezone.utc)
        current_end = user.subscription_end_date
        if current_end and current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=timezone.utc)

        new_end = current_end
        new_role = user.role

        if action == "add_days":
            d = int(days or 0)
            if d <= 0:
                raise BusinessValidationError("تعداد روز برای افزودن باید بزرگتر از صفر باشد.")
            base_dt = current_end if (current_end and current_end > now) else now
            new_end = base_dt + timedelta(days=d)
            if new_role != "ADMIN":
                new_role = "VIP"
        elif action == "sub_days":
            d = int(days or 0)
            if d <= 0:
                raise BusinessValidationError("تعداد روز برای کسر باید بزرگتر از صفر باشد.")
            base_dt = current_end or now
            new_end = base_dt - timedelta(days=d)
            if new_end <= now and new_role != "ADMIN":
                new_role = "USER"
        elif action == "set_date":
            if not exact_date:
                raise BusinessValidationError("تاریخ دقیق انقضای اشتراک الزامی است.")
            try:
                parsed = datetime.fromisoformat(exact_date.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise BusinessValidationError("فرمت تاریخ نامعتبر است (از YYYY-MM-DD استفاده کنید).") from exc
            new_end = parsed
            if new_role != "ADMIN":
                new_role = "VIP" if new_end > now else "USER"
        elif action == "revoke":
            new_end = None
            if new_role != "ADMIN":
                new_role = "USER"
        elif action == "set_role":
            target_role = (role or "").upper()
            if target_role not in ("USER", "VIP", "ADMIN"):
                raise BusinessValidationError("نقش کاربر نامعتبر است.")
            new_role = target_role
            if target_role == "USER":
                new_end = None
        else:
            raise BusinessValidationError("عملیات VIP نامعتبر است.")

        updated = await user_repo.update_vip_subscription(user, new_role, new_end)
        await sys_repo.add_audit_log(
            admin_id=admin_id,
            action="MANUAL_VIP_EDIT",
            target_id=str(target_user_id),
            details={
                "action": action,
                "days": days,
                "exact_date": exact_date,
                "new_role": new_role,
                "subscription_end_date": new_end.isoformat() if new_end else None,
            },
        )
        logger.info(f"Admin {admin_id} manual VIP edit ({action}) on user {target_user_id} -> role={new_role}, end={new_end}")
        return updated
