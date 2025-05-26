# handlers/__init__.py

from aiogram import Router

from . import start
from . import buying
from . import profile
from . import setup
from . import questions
from . import menu


def setup_routers() -> Router:
    """Настройка всех роутеров"""
    router = Router()

    # Подключаем все роутеры
    router.include_router(start.router)
    router.include_router(buying.router)
    router.include_router(profile.router)
    router.include_router(setup.router)
    router.include_router(questions.router)
    router.include_router(menu.router)

    return router