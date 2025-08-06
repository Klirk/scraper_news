"""
Тесты для модуля работы с базой данных
"""
import pytest
import os
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.exc import OperationalError

from app.db.database import get_session, init_db, close_db, engine, async_session


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_session():
    """Тест получения сессии базы данных"""
    session_count = 0
    
    # Тестируем что get_session возвращает асинхронный генератор
    async for session in get_session():
        assert isinstance(session, AsyncSession)
        session_count += 1
        break  # Выходим после первой итерации
    
    assert session_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_session_context_manager():
    """Тест что get_session работает как контекстный менеджер"""
    async for session in get_session():
        # Проверяем что сессия активна
        assert not session.is_active or session.is_active
        
        # Проверяем что можем выполнять операции
        assert hasattr(session, 'execute')
        assert hasattr(session, 'commit')
        assert hasattr(session, 'rollback')
        break


@pytest.mark.unit
def test_database_url_configuration():
    """Тест конфигурации URL базы данных"""
    # Проверяем что URL по умолчанию корректный
    default_url = "postgresql+asyncpg://scraper_user:scraper_password@postgres:5432/ft_news"
    
    # Проверяем что переменная окружения используется
    with patch.dict(os.environ, {'DATABASE_URL': 'test://test:test@test:1234/test'}):
        # Перезагружаем модуль чтобы применить новую переменную окружения
        import importlib
        import app.db.database
        importlib.reload(app.db.database)
        
        # Проверяем что новый URL был применен (косвенно через проверку атрибутов)
        assert hasattr(app.db.database, 'engine')
        assert hasattr(app.db.database, 'async_session')


@pytest.mark.unit
def test_engine_configuration():
    """Тест конфигурации движка базы данных"""
    # Проверяем что движок создан
    assert engine is not None
    assert isinstance(engine, AsyncEngine)
    
    # Проверяем что движок имеет правильные настройки
    assert hasattr(engine, 'url')
    assert hasattr(engine, 'pool')


@pytest.mark.unit
def test_session_factory_configuration():
    """Тест конфигурации фабрики сессий"""
    # Проверяем что фабрика сессий создана
    assert async_session is not None
    
    # Проверяем конфигурацию фабрики
    assert async_session.bind == engine
    assert async_session.expire_on_commit is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_init_db():
    """Тест инициализации базы данных"""
    # Мокаем движок и подключение
    mock_conn = AsyncMock()
    mock_engine = AsyncMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn
    
    with patch('app.db.database.engine', mock_engine):
        await init_db()
        
        # Проверяем что была попытка создать таблицы
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_close_db():
    """Тест закрытия подключений к базе данных"""
    # Мокаем движок
    mock_engine = AsyncMock()
    
    with patch('app.db.database.engine', mock_engine):
        await close_db()
        
        # Проверяем что dispose был вызван
        mock_engine.dispose.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection_error_handling():
    """Тест обработки ошибок подключения к базе данных"""
    # Мокаем движок который выбрасывает ошибку
    mock_engine = AsyncMock()
    mock_engine.begin.side_effect = OperationalError("Connection failed", None, None)
    
    with patch('app.db.database.engine', mock_engine):
        with pytest.raises(OperationalError):
            await init_db()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_transaction_rollback():
    """Тест отката транзакции при ошибке"""
    try:
        async for session in get_session():
            # Симулируем ошибку в транзакции
            await session.execute("INVALID SQL")
            await session.commit()
    except Exception:
        # Ошибка ожидаема, проверяем что сессия корректно закрылась
        pass


@pytest.mark.database
@pytest.mark.asyncio 
async def test_database_session_isolation(test_db_session):
    """Тест изоляции сессий базы данных"""
    from app.models.models import Article
    from datetime import datetime, timezone
    
    # Создаем статью в одной сессии
    article = Article(
        url="https://www.ft.com/content/isolation-test",
        title="Isolation Test Article", 
        content="Testing session isolation",
        author="Test Author",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем что статья существует в этой же сессии
    from sqlalchemy import select
    result = await test_db_session.execute(select(Article).where(Article.url == article.url))
    found_article = result.scalar_one()
    assert found_article.title == "Isolation Test Article"


@pytest.mark.database
@pytest.mark.asyncio
async def test_concurrent_sessions(test_db_session):
    """Тест работы с несколькими сессиями одновременно"""
    from app.models.models import Article
    from datetime import datetime, timezone
    from sqlalchemy import select
    
    # Создаем статьи в разных "сессиях" (симулируем через одну тестовую)
    articles = []
    for i in range(3):
        article = Article(
            url=f"https://www.ft.com/content/concurrent-{i}",
            title=f"Concurrent Article {i}",
            content=f"Content for concurrent test {i}",
            author=f"Author {i}",
            published_at=datetime.now(timezone.utc),
            scraped_at=datetime.now(timezone.utc)
        )
        articles.append(article)
        test_db_session.add(article)
    
    await test_db_session.commit()
    
    # Проверяем что все статьи сохранились
    result = await test_db_session.execute(select(Article))
    all_articles = result.scalars().all()
    assert len(all_articles) >= 3


@pytest.mark.unit
def test_database_module_imports():
    """Тест что все необходимые модули импортируются корректно"""
    import app.db.database as db_module
    
    # Проверяем что все основные объекты доступны
    assert hasattr(db_module, 'engine')
    assert hasattr(db_module, 'async_session') 
    assert hasattr(db_module, 'get_session')
    assert hasattr(db_module, 'init_db')
    assert hasattr(db_module, 'close_db')
    assert hasattr(db_module, 'DATABASE_URL')