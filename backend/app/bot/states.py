from aiogram.fsm.state import State, StatesGroup


class AlertFSM(StatesGroup):
    """FSM states for interactive price/percentage alert wizard."""
    choosing_pair = State()
    choosing_type = State()
    choosing_direction = State()
    entering_value = State()


class AdminFSM(StatesGroup):
    """FSM states for administrative commands."""
    entering_ban_user_id = State()
    entering_ban_reason = State()
