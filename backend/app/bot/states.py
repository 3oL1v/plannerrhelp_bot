from aiogram.fsm.state import State, StatesGroup


class PlannerStates(StatesGroup):
    waiting_for_task_title = State()
    waiting_for_task_date = State()
    waiting_for_task_custom_date = State()
    waiting_for_task_time = State()
    waiting_for_task_custom_time = State()
    waiting_for_event_title = State()
    waiting_for_event_date = State()
    waiting_for_event_custom_date = State()
    waiting_for_event_time = State()
    waiting_for_event_custom_time = State()
    waiting_for_event_duration = State()
    waiting_for_event_custom_duration = State()
    waiting_for_quick_note = State()
    waiting_for_reschedule = State()
