"""FSM-состояния пользователя."""

from telebot.handler_backends import State, StatesGroup


class UserState(StatesGroup):
    main_menu = State()
    choosing_topic = State()
    solving = State()
    waiting_next_task = State()
    waiting_feedback = State()
