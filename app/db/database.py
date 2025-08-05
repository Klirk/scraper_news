from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from typing import AsyncGenerator

# Строка подключения к PostgreSQL через asyncpg
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://scraper_user:scraper_password@postgres:5432/ft_news"
)

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

# Асинхронный dependency для FastAPI или ручного использования
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
        print("✅ Таблицы базы данных успешно созданы/обновлены")


# Функция для закрытия подключений
async def close_db() -> None:
    """Закрывает подключения к базе данных"""
    await engine.dispose()
    print("🔌 Подключения к базе данных закрыты")
