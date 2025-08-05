from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import os

# Пример строки подключения к PostgreSQL через asyncpg
DATABASE_URL = "postgresql+asyncpg://postgres:scraper_password@localhost:5432/ft_news"
# Создаём движок
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,  # лог SQL-запросов, можно отключить
)

# Сессии — через async_sessionmaker
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Базовый класс моделей
Base = declarative_base()

# Асинхронный dependency для FastAPI или ручного использования
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
