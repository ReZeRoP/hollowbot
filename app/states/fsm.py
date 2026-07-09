"""aiogram FSM state groups for multi-step flows."""
from aiogram.fsm.state import State, StatesGroup


class TopUpStates(StatesGroup):
    amount = State()          # waiting for top-up amount
    receipt = State()         # waiting for receipt photo


class PurchaseStates(StatesGroup):
    receipt = State()         # card-to-card receipt for a plan purchase


class SupportStates(StatesGroup):
    message = State()


class AdminStates(StatesGroup):
    broadcast = State()
    add_plan = State()
    add_panel = State()
    adjust_balance = State()
    reject_reason = State()
