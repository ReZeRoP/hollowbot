"""
Wallet ledger. Every balance change goes through `record()` so we always keep
an auditable transaction row and a correct running balance.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Transaction, TxType, User


async def record(
    db: AsyncSession,
    user: User,
    *,
    tx_type: TxType,
    amount: int,
    description: str | None = None,
    ref_payment_id: int | None = None,
    commit: bool = True,
) -> Transaction:
    """
    Apply `amount` (positive=credit, negative=debit) to the user's balance and
    log a Transaction. Raises ValueError on insufficient funds for debits.
    """
    new_balance = user.balance + amount
    if new_balance < 0:
        raise ValueError("insufficient_balance")

    user.balance = new_balance
    tx = Transaction(
        user_id=user.id,
        type=tx_type,
        amount=amount,
        balance_after=new_balance,
        description=description,
        ref_payment_id=ref_payment_id,
    )
    db.add(tx)
    if commit:
        await db.commit()
        await db.refresh(tx)
    return tx


async def can_afford(user: User, amount: int) -> bool:
    return user.balance >= amount
