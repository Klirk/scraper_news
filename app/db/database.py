"""
Модуль для работы с базой данных PostgreSQL с использованием SQLAlchemy и asyncpg.
Создаёт асинхронный движок, сессии и предоставляет функции для инициализации и закрытия базы данных.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from typing import AsyncGenerator
from loguru import logger

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://scraper_user:scraper_password@postgres:5432/ft_news"
)

# Создаём движок
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
)

# Создаём асинхронную сессию
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


# Генератор для получения сессии базы данных
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


# Функция для создания таблиц в базе данных
async def init_db() -> None:
    """Создает все таблицы в базе данных согласно моделям"""
    from app.models.models import Base

    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ База данных инициализирована")


# Функция для закрытия подключений
async def close_db() -> None:
    """Закрывает подключения к базе данных"""
    await engine.dispose()
    logger.info("🔌 Подключения к базе данных закрыты")
