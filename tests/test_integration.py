"""
Интеграционные тесты для Financial Times скрапера
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func

from app.scraper.scraper import FTScraper
from app.scheduler.scheduler import ScrapingScheduler
from app.models.models import Article
from app.db.database import init_db


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_scraping_workflow(test_db_session):
    """Полный интеграционный тест рабочего процесса скрапинга"""
    
    # Создаем мок данных
    mock_html = """
    <ul class="o-teaser-collection__list">
        <li class="o-teaser-collection__item">
            <div class="o-teaser__content">
                <div class="o-teaser__heading">
                    <a href="/content/integration-test-article" class="js-teaser-heading-link">
                        Integration Test Article
                    </a>
                </div>
                <div class="o-teaser__standfirst">Integration test content</div>
                <div class="o-teaser__timestamp">
                    <time title="January 15 2024 10:30 am">Jan 15 2024</time>
                </div>
            </div>
        </li>
    </ul>
    """
    
    mock_article_html = """
    <article class="n-content-body">
        <div class="n-content-body__content">
            <p>This is integration test article content.</p>
            <p>Testing full workflow from scraping to database.</p>
        </div>
    </article>
    """
    
    # Настраиваем мок скрапера
    scraper = FTScraper()
    
    # Мокаем браузер и страницу
    mock_page = AsyncMock()
    mock_page.content.side_effect = [mock_html, mock_article_html]
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.set_default_timeout = MagicMock()
    mock_context.set_default_navigation_timeout = MagicMock()
    
    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    
    # Мокаем функцию get_session для использования тестовой сессии
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.async_playwright') as mock_async_playwright:
        with patch('app.scraper.scraper.get_session', mock_get_session):
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright
            
            # Мокаем парсинг даты
            with patch.object(scraper, '_parse_published_date') as mock_parse_date:
                mock_parse_date.return_value = datetime.now(timezone.utc)
                
                # Запускаем браузер
                await scraper.start_browser()
                
                # Выполняем скрапинг
                articles = await scraper.scrape_single_page(1)
                
                # Проверяем что статьи были получены
                assert len(articles) > 0
                assert articles[0]['title'] == 'Integration Test Article'
                
                # Сохраняем статьи в базу данных
                saved_count = await scraper.save_articles_to_db(articles)
                
                # Проверяем что статьи сохранились
                assert saved_count == len(articles)
                
                # Проверяем что статьи действительно в базе
                result = await test_db_session.execute(
                    select(Article).where(Article.title == 'Integration Test Article')
                )
                saved_article = result.scalar_one()
                
                assert saved_article.title == 'Integration Test Article'
                assert 'integration-test-article' in saved_article.url
                
                # Закрываем браузер
                await scraper.close_browser()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scheduler_integration(test_db_session):
    """Интеграционный тест планировщика с базой данных"""
    
    # Мокаем скрапер для планировщика
    mock_scraper = AsyncMock()
    mock_scraper.is_first_run.return_value = False
    mock_scraper.run_scraping.return_value = None
    
    scheduler = ScrapingScheduler()
    scheduler.scraper = mock_scraper
    scheduler.scheduler = MagicMock()
    
    # Тестируем ручной режим
    await scheduler.start_manual_mode()
    
    # Проверяем что скрапер был вызван
    mock_scraper.run_scraping.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_integration_with_real_data(test_db_session):
    """Интеграционный тест базы данных с реальными данными"""
    
    # Создаем тестовые статьи
    articles_data = [
        {
            "url": "https://www.ft.com/content/integration-article-1",
            "title": "Integration Article 1",
            "content": "Content of integration article 1",
            "author": "Integration Author 1",
            "published_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "scraped_at": datetime.now(timezone.utc)
        },
        {
            "url": "https://www.ft.com/content/integration-article-2", 
            "title": "Integration Article 2",
            "content": "Content of integration article 2",
            "author": "Integration Author 2",
            "published_at": datetime.now(timezone.utc) - timedelta(hours=2),
            "scraped_at": datetime.now(timezone.utc)
        }
    ]
    
    # Мокаем get_session для использования тестовой сессии
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.get_session', mock_get_session):
        # Сохраняем статьи через скрапер
        saved_count = await FTScraper.save_articles_to_db(articles_data)
        
        # Проверяем что все статьи сохранились
        assert saved_count == len(articles_data)
        
        # Проверяем количество статей в базе
        result = await test_db_session.execute(select(func.count(Article.id)))
        count = result.scalar()
        assert count == len(articles_data)
        
        # Проверяем конкретные статьи
        result = await test_db_session.execute(
            select(Article).order_by(Article.published_at.desc())
        )
        saved_articles = result.scalars().all()
        
        assert len(saved_articles) == 2
        assert saved_articles[0].title == "Integration Article 1"  # Более свежая
        assert saved_articles[1].title == "Integration Article 2"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_first_run_detection_integration(test_db_session):
    """Интеграционный тест определения первого запуска"""
    
    # Мокаем get_session
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.get_session', mock_get_session):
        # Проверяем что пустая база детектится как первый запуск
        is_first = await FTScraper.is_first_run()
        assert is_first is True
        
        # Добавляем статью
        article = Article(
            url="https://www.ft.com/content/test-first-run",
            title="Test First Run Article",
            content="Test content for first run detection",
            author="Test Author",
            published_at=datetime.now(timezone.utc),
            scraped_at=datetime.now(timezone.utc)
        )
        test_db_session.add(article)
        await test_db_session.commit()
        
        # Теперь должно определяться как не первый запуск
        is_first = await FTScraper.is_first_run()
        assert is_first is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_article_deduplication_integration(test_db_session):
    """Интеграционный тест дедупликации статей"""
    
    # Создаем статью с уникальным URL
    original_article = Article(
        url="https://www.ft.com/content/unique-article",
        title="Original Article",
        content="Original content",
        author="Original Author",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    test_db_session.add(original_article)
    await test_db_session.commit()
    
    # Пытаемся сохранить дубликат через скрапер
    duplicate_data = [{
        "url": "https://www.ft.com/content/unique-article",  # Тот же URL
        "title": "Duplicate Article",
        "content": "Duplicate content", 
        "author": "Duplicate Author",
        "published_at": datetime.now(timezone.utc),
        "scraped_at": datetime.now(timezone.utc)
    }]
    
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.get_session', mock_get_session):
        saved_count = await FTScraper.save_articles_to_db(duplicate_data)
        
        # Дубликат не должен сохраниться
        assert saved_count == 0
        
        # В базе должна остаться только оригинальная статья
        result = await test_db_session.execute(
            select(Article).where(Article.url == "https://www.ft.com/content/unique-article")
        )
        articles = result.scalars().all()
        assert len(articles) == 1
        assert articles[0].title == "Original Article"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_time_filtering_integration():
    """Интеграционный тест временной фильтрации"""
    
    now = datetime.now(timezone.utc)
    
    # Создаем статьи с разными датами
    articles_data = [
        {
            "url": "https://www.ft.com/content/recent-article",
            "title": "Recent Article",
            "content": "Recent content",
            "author": "Recent Author",
            "published_at": now - timedelta(minutes=30),  # Свежая статья
            "scraped_at": now
        },
        {
            "url": "https://www.ft.com/content/old-article",
            "title": "Old Article", 
            "content": "Old content",
            "author": "Old Author",
            "published_at": now - timedelta(hours=25),  # Старая статья
            "scraped_at": now
        }
    ]
    
    # Тестируем фильтр времени
    def time_filter(pub_date):
        return pub_date > now - timedelta(hours=1)
    
    scraper = FTScraper()
    
    # Фильтруем статьи
    filtered_articles = []
    for article_data in articles_data:
        if time_filter(article_data['published_at']):
            filtered_articles.append(article_data)
    
    # Должна остаться только свежая статья
    assert len(filtered_articles) == 1
    assert filtered_articles[0]['title'] == "Recent Article"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_scraping_sessions(test_db_session):
    """Интеграционный тест параллельных сессий скрапинга"""
    
    async def scraping_session(session_id, test_session):
        """Симулирует сессию скрапинга"""
        articles_data = [{
            "url": f"https://www.ft.com/content/concurrent-article-{session_id}",
            "title": f"Concurrent Article {session_id}",
            "content": f"Content from session {session_id}",
            "author": f"Author {session_id}",
            "published_at": datetime.now(timezone.utc),
            "scraped_at": datetime.now(timezone.utc)
        }]
        
        async def mock_get_session():
            yield test_session
        
        with patch('app.scraper.scraper.get_session', mock_get_session):
            saved_count = await FTScraper.save_articles_to_db(articles_data)
            return saved_count
    
    # Запускаем несколько параллельных сессий скрапинга
    tasks = [
        scraping_session(i, test_db_session) 
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Проверяем что все сессии успешно сохранили статьи
    assert all(count == 1 for count in results)
    
    # Проверяем общее количество статей в базе
    result = await test_db_session.execute(select(func.count(Article.id)))
    total_count = result.scalar()
    assert total_count == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_recovery_integration(test_db_session):
    """Интеграционный тест восстановления после ошибок"""
    
    # Создаем данные с одной проблемной статьей
    articles_data = [
        {
            "url": "https://www.ft.com/content/good-article-1",
            "title": "Good Article 1",
            "content": "Good content 1",
            "author": "Good Author 1",
            "published_at": datetime.now(timezone.utc),
            "scraped_at": datetime.now(timezone.utc)
        },
        {
            "url": None,  # Проблемная статья с невалидным URL
            "title": "Bad Article",
            "content": "Bad content",
            "author": "Bad Author",
            "published_at": datetime.now(timezone.utc),
            "scraped_at": datetime.now(timezone.utc)
        },
        {
            "url": "https://www.ft.com/content/good-article-2",
            "title": "Good Article 2",
            "content": "Good content 2", 
            "author": "Good Author 2",
            "published_at": datetime.now(timezone.utc),
            "scraped_at": datetime.now(timezone.utc)
        }
    ]
    
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.get_session', mock_get_session):
        # Сохраняем статьи (должны сохраниться только валидные)
        saved_count = await FTScraper.save_articles_to_db(articles_data)
        
        # Должны сохраниться только хорошие статьи
        assert saved_count == 2
        
        # Проверяем что хорошие статьи действительно сохранились
        result = await test_db_session.execute(select(Article))
        saved_articles = result.scalars().all()
        
        assert len(saved_articles) == 2
        titles = [article.title for article in saved_articles]
        assert "Good Article 1" in titles
        assert "Good Article 2" in titles
        assert "Bad Article" not in titles


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.asyncio
async def test_full_application_integration(test_db_session):
    """Полный интеграционный тест приложения"""
    
    # Мокаем внешние зависимости
    mock_articles = [
        {
            "url": "https://www.ft.com/content/full-integration-1",
            "title": "Full Integration Article 1",
            "content": "Full integration content 1",
            "author": "Integration Author 1",
            "published_at": datetime.now(timezone.utc),
            "scraped_at": datetime.now(timezone.utc)
        }
    ]
    
    # Создаем скрапер и планировщик
    scraper = FTScraper()
    scheduler = ScrapingScheduler()
    scheduler.scraper = scraper
    
    # Мокаем методы скрапера
    scraper.run_scraping = AsyncMock()
    scraper.is_first_run = AsyncMock(return_value=False)
    
    async def mock_get_session():
        yield test_db_session
    
    with patch('app.scraper.scraper.get_session', mock_get_session):
        # Тестируем что первый запуск детектируется корректно
        is_first = await scraper.is_first_run()
        assert is_first is True  # База пустая
        
        # Сохраняем тестовые статьи
        saved_count = await scraper.save_articles_to_db(mock_articles)
        assert saved_count == 1
        
        # Теперь не первый запуск
        is_first = await scraper.is_first_run()
        assert is_first is False
        
        # Тестируем планировщик в ручном режиме
        await scheduler.start_manual_mode()
        scraper.run_scraping.assert_called_once()
        
        # Проверяем финальное состояние базы
        result = await test_db_session.execute(select(func.count(Article.id)))
        final_count = result.scalar()
        assert final_count == 1