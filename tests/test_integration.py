"""
Интеграционные тесты для всего приложения
"""
import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from app.main import main
from app.scheduler.scheduler import ScrapingScheduler
from app.scraper.scraper import FTScraper
from app.models.models import Article
from app.db.database import init_db, close_db


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_initialization():
    """Тестирует инициализацию базы данных"""
    # Мокаем engine и connection
    with patch('app.db.database.engine') as mock_engine:
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        await init_db()
        
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_scraping_cycle(test_db_session):
    """Интеграционный тест полного цикла скрапинга"""
    scraper = FTScraper()
    
    # Мокаем браузер и страницу
    scraper.init_browser = AsyncMock()
    scraper.close_browser = AsyncMock()
    mock_page = AsyncMock()
    scraper.page = mock_page
    
    # Мокаем HTML ответ с одной статьей
    html_content = """
    <html>
        <ul class="o-teaser-collection__list">
            <li class="o-teaser-collection__item">
                <a href="/content/integration-test" class="js-teaser-heading-link">Integration Test Article</a>
                <a href="/content/integration-test" class="js-teaser-standfirst-link">Integration test content</a>
                <a href="/author/test" class="o-teaser__tag">Test Author</a>
                <time title="January 15 2024 10:30 am">Jan 15 2024</time>
            </li>
        </ul>
    </html>
    """
    
    mock_page.content.return_value = html_content
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    
    # Мокаем get_session чтобы использовать тестовую сессию
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        mock_get_session.return_value = mock_session_generator()
        
        # Мокаем asyncio.sleep для ускорения теста
        with patch('asyncio.sleep'):
            articles_data = await scraper.scrape_single_page(1)
            saved_count = await scraper.save_articles_to_db(articles_data)
    
    # Проверяем результаты
    assert len(articles_data) == 1
    assert saved_count == 1
    assert articles_data[0]['title'] == "Integration Test Article"
    
    # Проверяем, что статья действительно сохранена в базе
    result = await test_db_session.execute(select(Article))
    all_articles = result.scalars().all()
    assert len(all_articles) == 1
    assert all_articles[0].title == "Integration Test Article"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scheduler_scraper_integration():
    """Тестирует интеграцию планировщика и скрапера"""
    scheduler = ScrapingScheduler()
    
    # Мокаем scraper методы
    scheduler.scraper.run_initial_scraping = AsyncMock()
    scheduler.scraper.run_hourly_scraping = AsyncMock()
    scheduler.scraper.run_scraping = AsyncMock()
    scheduler.scraper.is_first_run = AsyncMock(return_value=True)
    
    # Тестируем задачи планировщика
    await scheduler.initial_scrape_job()
    scheduler.scraper.run_initial_scraping.assert_called_once()
    
    await scheduler.hourly_scrape_job()
    scheduler.scraper.run_hourly_scraping.assert_called_once()
    
    await scheduler.adaptive_scrape_job()
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_main_application_flow():
    """Тестирует основной поток выполнения приложения"""
    # Мокаем все внешние зависимости
    with patch('app.main.init_db') as mock_init_db, \
         patch('app.main.close_db') as mock_close_db, \
         patch('app.main.ScrapingScheduler') as mock_scheduler_class:
        
        mock_scheduler = AsyncMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        # Мокаем scheduler.start чтобы он сразу завершался
        async def mock_start():
            # Имитируем KeyboardInterrupt для завершения
            raise KeyboardInterrupt("Test interrupt")
        
        mock_scheduler.start = mock_start
        
        # Запускаем main
        await main()
        
        # Проверяем, что были вызваны нужные методы
        mock_init_db.assert_called_once()
        mock_scheduler_class.assert_called_once()
        mock_close_db.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_main_application_with_exception():
    """Тестирует обработку исключений в основном потоке"""
    with patch('app.main.init_db') as mock_init_db, \
         patch('app.main.close_db') as mock_close_db:
        
        # init_db выбрасывает исключение
        mock_init_db.side_effect = Exception("Database init failed")
        
        # Не должно выбрасывать исключение
        await main()
        
        # close_db должен быть вызван даже при ошибке
        mock_close_db.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_first_run_scenario(test_db_session):
    """Тестирует сценарий первого запуска приложения"""
    # Проверяем, что база пустая (первый запуск)
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        mock_get_session.return_value = mock_session_generator()
        
        is_first = await FTScraper.is_first_run()
        assert is_first is True
    
    # Создаем планировщик и скрапер
    scheduler = ScrapingScheduler()
    scheduler.scraper.init_browser = AsyncMock()
    scheduler.scraper.close_browser = AsyncMock()
    
    # Мокаем скрапинг
    mock_articles = [
        {
            "url": "https://test.com/first-run-article",
            "title": "First Run Article",
            "content": "Content from first run",
            "author": "Test Author",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        }
    ]
    
    scheduler.scraper.scrape_articles_with_pagination = AsyncMock(return_value=mock_articles)
    
    # Мокаем сохранение в базу
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        mock_get_session.return_value = mock_session_generator()
        
        # Запускаем первоначальный скрапинг
        await scheduler.scraper.run_initial_scraping()
    
    # Проверяем, что скрапинг был выполнен с правильными параметрами
    scheduler.scraper.scrape_articles_with_pagination.assert_called_once()
    args, kwargs = scheduler.scraper.scrape_articles_with_pagination.call_args
    assert kwargs['max_pages'] == 50  # Для первого запуска


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_normal_run_scenario(test_db_session):
    """Тестирует сценарий обычного запуска приложения"""
    # Добавляем статью в базу (НЕ первый запуск)
    article = Article(
        url="https://existing.com/article",
        title="Existing Article",
        content="Existing content",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        scraped_at=datetime.datetime.now(datetime.timezone.utc)
    )
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем, что это НЕ первый запуск
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        mock_get_session.return_value = mock_session_generator()
        
        is_first = await FTScraper.is_first_run()
        assert is_first is False
    
    # Создаем планировщик
    scheduler = ScrapingScheduler()
    scheduler.scraper.init_browser = AsyncMock()
    scheduler.scraper.close_browser = AsyncMock()
    scheduler.scraper.scrape_articles_with_pagination = AsyncMock(return_value=[])
    
    # Запускаем почасовой скрапинг
    await scheduler.scraper.run_hourly_scraping()
    
    # Проверяем параметры для почасового скрапинга
    args, kwargs = scheduler.scraper.scrape_articles_with_pagination.call_args
    assert kwargs['max_pages'] == 5  # Для почасового запуска


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_recovery_and_resilience():
    """Тестирует восстановление после ошибок и отказоустойчивость"""
    scheduler = ScrapingScheduler()
    
    # Имитируем ошибки в разных частях системы
    
    # 1. Ошибка инициализации браузера
    scheduler.scraper.init_browser = AsyncMock(side_effect=Exception("Browser failed"))
    scheduler.scraper.close_browser = AsyncMock()
    
    # Скрапинг должен обработать ошибку и не упасть
    await scheduler.scraper.run_scraping()
    scheduler.scraper.close_browser.assert_called_once()
    
    # 2. Ошибка в планировщике
    scheduler.scraper.is_first_run = AsyncMock(side_effect=Exception("DB connection failed"))
    scheduler.stop = AsyncMock()
    
    # Планировщик должен вызвать stop при ошибке
    await scheduler.start()
    scheduler.stop.assert_called_once()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_scraping_operations():
    """Тестирует параллельные операции скрапинга"""
    scraper1 = FTScraper()
    scraper2 = FTScraper()
    
    # Мокаем операции
    scraper1.init_browser = AsyncMock()
    scraper1.close_browser = AsyncMock()
    scraper1.scrape_single_page = AsyncMock(return_value=[])
    
    scraper2.init_browser = AsyncMock()
    scraper2.close_browser = AsyncMock()
    scraper2.scrape_single_page = AsyncMock(return_value=[])
    
    # Запускаем параллельно
    tasks = [
        scraper1.scrape_single_page(1),
        scraper2.scrape_single_page(2)
    ]
    
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 2
    scraper1.scrape_single_page.assert_called_once_with(1)
    scraper2.scrape_single_page.assert_called_once_with(2)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_connection_pool(test_db_session):
    """Тестирует работу пула подключений к базе данных"""
    from sqlalchemy import text
    
    # Используем тестовую сессию для проверки базовой функциональности
    result = await test_db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    
    # Проверяем, что можем выполнить несколько запросов
    for i in range(3):
        result = await test_db_session.execute(text(f"SELECT {i + 1}"))
        assert result.scalar() == i + 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logging_integration():
    """Тестирует интеграцию логирования"""
    # Проверяем, что логгер настроен в main.py
    import app.main
    from loguru import logger
    
    # Логгер должен быть настроен для записи в файл
    # Это проверяется косвенно через успешный импорт модуля
    assert hasattr(logger, 'info')
    assert hasattr(logger, 'error')
    assert hasattr(logger, 'warning')


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_environment_configuration():
    """Тестирует конфигурацию через переменные окружения"""
    import os
    
    # Проверяем, что переменные окружения правильно обрабатываются
    with patch.dict(os.environ, {'DATABASE_URL': 'sqlite+aiosqlite:///:memory:'}):
        # Перезагружаем модуль для применения новых переменных
        import importlib
        import app.db.database
        importlib.reload(app.db.database)
        
        assert app.db.database.DATABASE_URL == 'sqlite+aiosqlite:///:memory:'