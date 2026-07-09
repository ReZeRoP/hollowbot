"""
Full relational schema for the VPN sales bot.

Tables:
  users           – Telegram users, roles, wallet balance, referral link
  panels          – 3X-UI servers/panels (multi-server support)
  inbounds        – cached inbounds per panel (VLESS/VMess/... entry points)
  plans           – purchasable plans (volume/duration/price) mapped to inbounds
  plan_inbounds   – M2M association plan <-> inbound
  subscriptions   – a user's provisioned config on a panel (client on 3X-UI)
  transactions    – ledger for every wallet movement (topup/purchase/reward/refund)
  referrals       – inviter/invitee relationships + reward accounting
  payments        – card-to-card receipts awaiting/after admin approval
  settings        – runtime-editable key/value settings (mirrors .env defaults)
  discount_codes  – promo codes
  tickets         – support messages

All money is stored in the smallest sane integer unit (Toman, integer) to avoid
float rounding. Traffic is stored in BYTES (int) to match the 3X-UI API.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware UTC now (never use utcnow())."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
#  Enums
# --------------------------------------------------------------------------- #
class UserRole(str, enum.Enum):
    USER = "user"
    RESELLER = "reseller"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class SubStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"
    PENDING = "pending"


class SubKind(str, enum.Enum):
    FREE = "free"      # monthly free config
    PAID = "paid"      # purchased plan
    REFERRAL = "referral"


class TxType(str, enum.Enum):
    TOPUP = "topup"            # wallet top-up (card-to-card)
    PURCHASE = "purchase"      # spent buying a plan
    REFERRAL_REWARD = "referral_reward"
    REFUND = "refund"
    ADMIN_ADJUST = "admin_adjust"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentPurpose(str, enum.Enum):
    WALLET_TOPUP = "wallet_topup"
    PLAN_PURCHASE = "plan_purchase"


# --------------------------------------------------------------------------- #
#  Association table: plan <-> inbound (a plan can span multiple inbounds)
# --------------------------------------------------------------------------- #
plan_inbounds = Table(
    "plan_inbounds",
    Base.metadata,
    Column("plan_id", ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True),
    Column("inbound_id", ForeignKey("inbounds.id", ondelete="CASCADE"), primary_key=True),
)


# --------------------------------------------------------------------------- #
#  Users
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)

    # Wallet balance in Toman (integer).
    balance: Mapped[int] = mapped_column(BigInteger, default=0)

    # Referral bookkeeping
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    bonus_gb: Mapped[float] = mapped_column(Float, default=0.0)  # extra free GB earned

    # Anti-fraud / account age signals
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[str | None] = mapped_column(String(255))

    # Reseller custom pricing multiplier (1.0 = normal)
    price_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # relationships
    referred_by = relationship("User", remote_side=[id], backref="invitees")
    subscriptions = relationship("Subscription", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

    def is_admin(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)


# --------------------------------------------------------------------------- #
#  Panels (multi-server) + inbounds
# --------------------------------------------------------------------------- #
class Panel(Base):
    __tablename__ = "panels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(255))     # https://host:port/path
    username: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))

    # Public connection host (may differ from panel host, e.g. behind CDN).
    public_host: Mapped[str] = mapped_column(String(255))
    # Subscription server settings (if enabled on the panel).
    sub_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sub_base_url: Mapped[str | None] = mapped_column(String(255))  # https://host:2096/sub/

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # naive load-balancing weight (higher = gets more users)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    inbounds = relationship("Inbound", back_populates="panel", cascade="all, delete")


class Inbound(Base):
    """Cached snapshot of a 3X-UI inbound used to build configs."""

    __tablename__ = "inbounds"
    __table_args__ = (UniqueConstraint("panel_id", "inbound_id", name="uq_panel_inbound"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"))
    inbound_id: Mapped[int] = mapped_column(Integer)   # id on the panel
    remark: Mapped[str | None] = mapped_column(String(255))
    protocol: Mapped[str | None] = mapped_column(String(32))   # vless/vmess/trojan/ss
    port: Mapped[int | None] = mapped_column(Integer)
    # Raw streamSettings/security fields cached as JSON text for sub-link building.
    stream_settings: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    panel = relationship("Panel", back_populates="inbounds")
    plans = relationship("Plan", secondary=plan_inbounds, back_populates="inbounds")


# --------------------------------------------------------------------------- #
#  Plans
# --------------------------------------------------------------------------- #
class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    volume_gb: Mapped[float] = mapped_column(Float)          # 0 = unlimited
    duration_days: Mapped[int] = mapped_column(Integer)      # 0 = unlimited
    price: Mapped[int] = mapped_column(BigInteger)           # Toman
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    inbounds = relationship("Inbound", secondary=plan_inbounds, back_populates="plans")
    subscriptions = relationship("Subscription", back_populates="plan")


# --------------------------------------------------------------------------- #
#  Subscriptions (provisioned clients on a panel)
# --------------------------------------------------------------------------- #
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id"))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"))

    kind: Mapped[SubKind] = mapped_column(Enum(SubKind), default=SubKind.PAID)
    status: Mapped[SubStatus] = mapped_column(Enum(SubStatus), default=SubStatus.PENDING)

    # 3X-UI client identity
    client_uuid: Mapped[str] = mapped_column(String(64), index=True)   # VLESS/VMess uuid or trojan password
    client_email: Mapped[str] = mapped_column(String(128), index=True) # unique client "email"/remark on panel
    sub_id: Mapped[str | None] = mapped_column(String(64))             # subId for subscription server

    # Quota & usage (bytes)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)    # 0 = unlimited
    up_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    down_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Alerting flags (so we don't spam users)
    warned_volume: Mapped[bool] = mapped_column(Boolean, default=False)
    warned_expiry: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cached built subscription link
    sub_link: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    panel = relationship("Panel")

    @property
    def used_bytes(self) -> int:
        return self.up_bytes + self.down_bytes


# --------------------------------------------------------------------------- #
#  Transactions (wallet ledger)
# --------------------------------------------------------------------------- #
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[TxType] = mapped_column(Enum(TxType))
    amount: Mapped[int] = mapped_column(BigInteger)   # +credit / -debit (Toman)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str | None] = mapped_column(String(255))
    ref_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="transactions")


# --------------------------------------------------------------------------- #
#  Referrals
# --------------------------------------------------------------------------- #
class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("invitee_id", name="uq_invitee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bonus_gb_granted: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_earned: Mapped[int] = mapped_column(BigInteger, default=0)  # Toman from top-up %
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
#  Payments (card-to-card receipts)
# --------------------------------------------------------------------------- #
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[PaymentPurpose] = mapped_column(Enum(PaymentPurpose))
    amount: Mapped[int] = mapped_column(BigInteger)   # Toman
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)

    # Telegram file_id of the uploaded receipt photo
    receipt_file_id: Mapped[str | None] = mapped_column(String(255))
    # message id in admin group (so we can edit the approval buttons)
    admin_message_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)   # admin telegram id
    review_note: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------- #
#  Discount codes
# --------------------------------------------------------------------------- #
class DiscountCode(Base):
    __tablename__ = "discount_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    percent: Mapped[int] = mapped_column(Integer, default=0)     # 0-100
    max_uses: Mapped[int] = mapped_column(Integer, default=0)    # 0 = unlimited
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------- #
#  Support tickets
# --------------------------------------------------------------------------- #
class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(Text)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    admin_reply: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- #
#  Runtime settings (key/value) — editable from admin panel
# --------------------------------------------------------------------------- #
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
