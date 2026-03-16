from aiogram.fsm.state import State, StatesGroup


class PlannerStates(StatesGroup):
    waiting_for_task = State()
    waiting_for_event = State()
    waiting_for_quick_note = State()
    waiting_for_reschedule = State()
