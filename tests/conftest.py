"""
Конфигурация тестов и общие фикстуры
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.models import Base
from app.scraper.scraper import FTScraper


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всей сессии тестов"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Создает тестовую сессию базы данных в памяти"""
    # Создаем тестовую базу данных в памяти
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем фабрику сессий
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Создаем сессию для теста
    async with async_session() as session:
        yield session
    
    # Закрываем движок после теста
    await engine.dispose()


@pytest.fixture
def mock_browser():
    """Мок браузера Playwright"""
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()
    
    browser.new_context.return_value = context
    context.new_page.return_value = page
    
    return browser, context, page


@pytest.fixture
def mock_playwright():
    """Мок Playwright"""
    playwright = AsyncMock()
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()
    
    playwright.chromium.launch.return_value = browser
    browser.new_context.return_value = context
    context.new_page.return_value = page
    
    return playwright, browser, context, page


@pytest.fixture
def sample_article_data():
    """Тестовые данные статьи"""
    return {
        "url": "https://www.ft.com/content/test-article-123",
        "title": "Test Article Title",
        "content": "This is a test article content that should be long enough to be meaningful.",
        "author": "Test Author",
        "published_at": "2024-01-15T10:30:00+00:00"
    }


@pytest.fixture
def sample_articles_list():
    """Список тестовых статей"""
    return [
        {
            "url": "https://www.ft.com/content/article-1",
            "title": "First Test Article",
            "content": "Content of the first test article.",
            "author": "Author One",
            "published_at": "2024-01-15T10:30:00+00:00"
        },
        {
            "url": "https://www.ft.com/content/article-2",
            "title": "Second Test Article",
            "content": "Content of the second test article.",
            "author": "Author Two",
            "published_at": "2024-01-15T11:30:00+00:00"
        },
        {
            "url": "https://www.ft.com/content/article-3",
            "title": "Third Test Article",
            "content": "Content of the third test article.",
            "author": "Author Three",
            "published_at": "2024-01-15T12:30:00+00:00"
        }
    ]


@pytest.fixture
def mock_html_content():
    """Мок HTML контента страницы Financial Times"""
    return """
    <html>
    <body>
        <ul class="o-teaser-collection__list">
            <li class="o-teaser-collection__item">
                <div class="o-teaser__content">
                    <div class="o-teaser__heading">
                        <a href="/content/test-article-1" class="js-teaser-heading-link">
                            Test Article 1
                        </a>
                    </div>
                    <div class="o-teaser__standfirst">
                        Test standfirst content 1
                    </div>
                    <div class="o-teaser__timestamp">
                        <time title="January 15 2024 10:30 am">Jan 15 2024</time>
                    </div>
                </div>
            </li>
            <li class="o-teaser-collection__item">
                <div class="o-teaser__content">
                    <div class="o-teaser__heading">
                        <a href="/content/test-article-2" class="js-teaser-heading-link">
                            Test Article 2
                        </a>
                    </div>
                    <div class="o-teaser__standfirst">
                        Test standfirst content 2
                    </div>
                    <div class="o-teaser__timestamp">
                        <time title="January 15 2024 11:30 am">Jan 15 2024</time>
                    </div>
                </div>
            </li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def mock_article_html():
    """Мок HTML контента отдельной статьи"""
    return """
    <html>
    <body>
        <article class="n-content-body">
            <div class="article-info">
                <h1 class="o-typography-headline--large">Test Article Title</h1>
                <div class="article-info__timestamp">
                    <time title="January 15 2024 10:30 am">January 15, 2024</time>
                </div>
                <div class="article-info__author">
                    <span>By Test Author</span>
                </div>
            </div>
            <div class="n-content-body__content">
                <p>This is the first paragraph of the test article.</p>
                <p>This is the second paragraph with more content.</p>
                <p>And this is the final paragraph of the article.</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest_asyncio.fixture
async def scraper_with_mock_db(test_db_session, mock_playwright):
    """Скрапер с мок базой данных"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    
    # Мокаем функцию get_session чтобы она возвращала тестовую сессию
    async def mock_get_session():
        yield test_db_session
    
    # Заменяем get_session на наш мок
    import app.scraper.scraper
    original_get_session = app.scraper.scraper.get_session
    app.scraper.scraper.get_session = mock_get_session
    
    try:
        scraper = FTScraper()
        scraper.playwright = playwright_mock
        scraper.browser = browser_mock
        scraper.page = page_mock
        yield scraper
    finally:
        # Восстанавливаем оригинальную функцию
        app.scraper.scraper.get_session = original_get_session


# Помечаем все асинхронные тесты
pytest_plugins = ('pytest_asyncio',)