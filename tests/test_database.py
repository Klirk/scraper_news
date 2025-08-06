"""
Тесты для модуля работы с базой данных
"""
import pytest
import os
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_session, init_db, close_db, engine, async_session


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_session():
    """Тестирует генератор сессии базы данных"""
    session_generator = get_session()
    session = await session_generator.__anext__()
    
    assert isinstance(session, AsyncSession)
    
    # Закрываем сессию
    try:
        await session_generator.__anext__()
    except StopAsyncIteration:
        pass  # Ожидается исключение при завершении генератора


@pytest.mark.unit
@pytest.mark.asyncio
async def test_init_db():
    """Тестирует инициализацию базы данных"""
    with patch('app.db.database.engine') as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        await init_db()
        
        # Проверяем, что были вызваны нужные методы
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_db():
    """Тестирует закрытие подключений к базе данных"""
    with patch('app.db.database.engine') as mock_engine:
        mock_engine.dispose = AsyncMock()
        await close_db()
        
        # Проверяем, что engine.dispose() был вызван
        mock_engine.dispose.assert_called_once()


@pytest.mark.unit
def test_database_url_from_env():
    """Тестирует получение URL базы данных из переменных окружения"""
    # Тестируем значение по умолчанию
    with patch.dict(os.environ, {}, clear=True):
        from app.db.database import DATABASE_URL
        # Импортируем заново чтобы получить актуальное значение
        import importlib
        import app.db.database
        importlib.reload(app.db.database)
        
        expected_default = "postgresql+asyncpg://scraper_user:scraper_password@postgres:5432/ft_news"
        assert app.db.database.DATABASE_URL == expected_default


@pytest.mark.unit
def test_database_url_custom():
    """Тестирует настройку URL базы данных через переменную окружения"""
    custom_url = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
    
    with patch.dict(os.environ, {'DATABASE_URL': custom_url}):
        # Перезагружаем модуль чтобы применить новую переменную окружения
        import importlib
        import app.db.database
        importlib.reload(app.db.database)
        
        assert app.db.database.DATABASE_URL == custom_url


@pytest.mark.unit
def test_engine_creation():
    """Тестирует создание движка базы данных"""
    from app.db.database import engine
    assert engine is not None
    assert str(engine.url).startswith('postgresql+asyncpg://')


@pytest.mark.unit
def test_async_session_factory():
    """Тестирует фабрику асинхронных сессий"""
    from app.db.database import async_session
    assert async_session is not None
    assert hasattr(async_session, '__call__')


@pytest.mark.database
@pytest.mark.asyncio
async def test_database_session_context_manager(test_db_session):
    """Тестирует использование сессии как контекстного менеджера"""
    # Тестируем, что сессия работает в контексте теста
    assert isinstance(test_db_session, AsyncSession)
    
    # Проверяем, что можем выполнить простой запрос
    from sqlalchemy import text
    result = await test_db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.database
@pytest.mark.asyncio
async def test_session_transaction_rollback(test_db_session):
    """Тестирует откат транзакции при ошибке"""
    from app.models.models import Article
    import datetime
    
    try:
        # Создаем статью
        article = Article(
            url="https://test.com/article",
            title="Test Article",
            content="Test content",
            published_at=datetime.datetime.now(datetime.timezone.utc),
            scraped_at=datetime.datetime.now(datetime.timezone.utc)
        )
        test_db_session.add(article)
        await test_db_session.commit()
        
        # Пытаемся создать статью с тем же URL (должно вызвать ошибку)
        duplicate_article = Article(
            url="https://test.com/article",  # Тот же URL
            title="Duplicate Article",
            content="Duplicate content",
            published_at=datetime.datetime.now(datetime.timezone.utc),
            scraped_at=datetime.datetime.now(datetime.timezone.utc)
        )
        test_db_session.add(duplicate_article)
        
        with pytest.raises(Exception):
            await test_db_session.commit()
        
        # Откатываем транзакцию
        await test_db_session.rollback()
        
        # Проверяем, что можем продолжить работу с сессией
        from sqlalchemy import text
        result = await test_db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1
        
    except Exception:
        await test_db_session.rollback()
        raise


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_database_operations(test_db_session):
    """Интеграционный тест реальных операций с базой данных"""
    from app.models.models import Article
    import datetime
    from sqlalchemy import select
    
    # Используем тестовую сессию
    session = test_db_session
    
    # Создаем статью
    article = Article(
        url="https://integration-test.com/article",
        title="Integration Test Article",
        content="Integration test content",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        scraped_at=datetime.datetime.now(datetime.timezone.utc)
    )
    
    session.add(article)
    await session.commit()
    
    # Ищем созданную статью
    result = await session.execute(
        select(Article).where(Article.url == "https://integration-test.com/article")
    )
    found_article = result.scalar_one_or_none()
    
    assert found_article is not None
    assert found_article.title == "Integration Test Article"
    
    # Удаляем статью для очистки
    await session.delete(found_article)
    await session.commit()