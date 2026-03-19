from aiogram.fsm.state import State, StatesGroup


class PlannerStates(StatesGroup):
    waiting_for_task_title = State()
    waiting_for_task_date = State()
    waiting_for_task_time = State()
    waiting_for_event_title = State()
    waiting_for_event_date = State()
    waiting_for_event_time = State()
