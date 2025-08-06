"""
Тесты для скрапера Financial Times
"""
import pytest
import datetime
from unittest.mock import AsyncMock, patch
from bs4 import BeautifulSoup

from app.scraper.scraper import FTScraper
from app.models.models import Article
from sqlalchemy import select


@pytest.mark.unit
def test_scraper_initialization():
    """Тестирует инициализацию скрапера"""
    scraper = FTScraper()
    
    assert scraper.base_url == "https://www.ft.com"
    assert scraper.world_url == "https://www.ft.com/world"
    assert scraper.browser is None
    assert scraper.page is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_init_browser_success():
    """Тестирует успешную инициализацию браузера"""
    scraper = FTScraper()
    
    with patch('app.scraper.scraper.async_playwright') as mock_playwright:
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start = AsyncMock(return_value=mock_playwright_instance)
        
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        await scraper.init_browser()
        
        assert scraper.browser == mock_browser
        assert scraper.page == mock_page
        mock_browser.new_context.assert_called_once()
        mock_context.set_default_timeout.assert_called_with(30000)
        mock_context.set_default_navigation_timeout.assert_called_with(30000)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_init_browser_retry_on_failure():
    """Тестирует повторные попытки при неудачной инициализации браузера"""
    scraper = FTScraper()
    
    with patch('app.scraper.scraper.async_playwright') as mock_playwright:
        # Первые две попытки неудачны, третья успешна
        mock_playwright.return_value.start = AsyncMock(side_effect=[
            Exception("First attempt failed"),
            Exception("Second attempt failed"),
            Exception("Third attempt failed")  # Все попытки неудачны
        ])
        
        # Мокаем asyncio.sleep чтобы не ждать
        with patch('asyncio.sleep'):
            # Должно завершиться ошибкой после 3 попыток
            with pytest.raises(Exception):
                await scraper.init_browser(max_retries=3)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_browser():
    """Тестирует закрытие браузера"""
    scraper = FTScraper()
    mock_browser = AsyncMock()
    scraper.browser = mock_browser
    
    await scraper.close_browser()
    
    mock_browser.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_browser_with_exception():
    """Тестирует обработку исключений при закрытии браузера"""
    scraper = FTScraper()
    mock_browser = AsyncMock()
    mock_browser.close.side_effect = Exception("Close error")
    scraper.browser = mock_browser
    
    # Не должно выбрасывать исключение
    await scraper.close_browser()
    
    mock_browser.close.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_first_run_true(test_db_session):
    """Тестирует определение первого запуска (пустая база)"""
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        
        mock_get_session.return_value = mock_session_generator()
        
        result = await FTScraper.is_first_run()
        
        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_first_run_false(test_db_session):
    """Тестирует определение НЕ первого запуска (есть статьи в базе)"""
    # Добавляем статью в тестовую базу
    article = Article(
        url="https://test.com/article",
        title="Test Article",
        content="Test content",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        scraped_at=datetime.datetime.now(datetime.timezone.utc)
    )
    test_db_session.add(article)
    await test_db_session.commit()
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        
        mock_get_session.return_value = mock_session_generator()
        
        result = await FTScraper.is_first_run()
        
        assert result is False


@pytest.mark.unit
def test_is_article_recent():
    """Тестирует проверку свежести статьи"""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Статья опубликована 30 минут назад (свежая)
    recent_date = now - datetime.timedelta(minutes=30)
    assert FTScraper._is_article_recent(recent_date, hours_limit=1) is True
    
    # Статья опубликована 2 часа назад (не свежая)
    old_date = now - datetime.timedelta(hours=2)
    assert FTScraper._is_article_recent(old_date, hours_limit=1) is False


@pytest.mark.unit
def test_is_article_within_days():
    """Тестирует проверку статьи в пределах дней"""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Статья опубликована 15 дней назад (в пределах 30 дней)
    within_date = now - datetime.timedelta(days=15)
    assert FTScraper._is_article_within_days(within_date, days_limit=30) is True
    
    # Статья опубликована 45 дней назад (вне пределов 30 дней)
    outside_date = now - datetime.timedelta(days=45)
    assert FTScraper._is_article_within_days(outside_date, days_limit=30) is False


@pytest.mark.unit
def test_parse_publish_date():
    """Тестирует парсинг даты публикации"""
    date_str = "January 15 2024 10:30 am"
    result = FTScraper._parse_publish_date(date_str)
    
    expected = datetime.datetime(2024, 1, 15, 10, 30, tzinfo=datetime.timezone.utc)
    assert result == expected


@pytest.mark.unit
def test_parse_publish_date_invalid():
    """Тестирует парсинг неверной даты"""
    invalid_date_str = "invalid date string"
    result = FTScraper._parse_publish_date(invalid_date_str)
    
    # Должна вернуться текущая дата
    now = datetime.datetime.now(datetime.timezone.utc)
    assert (now - result).total_seconds() < 5  # Разница менее 5 секунд


@pytest.mark.unit
def test_extract_article_data():
    """Тестирует извлечение данных статьи из HTML"""
    scraper = FTScraper()
    
    html = """
    <li class="o-teaser-collection__item">
        <div class="o-teaser__content">
            <a href="/content/test-article" class="js-teaser-heading-link">Test Article Title</a>
            <a href="/content/test-article" class="js-teaser-standfirst-link">Test standfirst content</a>
            <a href="/tag/test-author" class="o-teaser__tag">Test Author</a>
            <time title="January 15 2024 10:30 am">Jan 15 2024</time>
        </div>
    </li>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    article_element = soup.find('li', class_='o-teaser-collection__item')
    
    result = scraper._extract_article_data(article_element)
    
    assert result is not None
    assert result['url'] == "https://www.ft.com/content/test-article"
    assert result['title'] == "Test Article Title"
    assert result['content'] == "Test standfirst content"
    assert result['author'] == "Test Author"
    assert isinstance(result['published_at'], datetime.datetime)
    assert isinstance(result['scraped_at'], datetime.datetime)


@pytest.mark.unit
def test_extract_article_data_premium():
    """Тестирует пропуск премиум статей"""
    scraper = FTScraper()
    
    html = """
    <li class="o-teaser-collection__item">
        <span class="o-labels--premium">Premium</span>
        <div class="o-teaser__content">
            <a href="/content/premium-article" class="js-teaser-heading-link">Premium Article</a>
        </div>
    </li>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    article_element = soup.find('li', class_='o-teaser-collection__item')
    
    result = scraper._extract_article_data(article_element)
    
    assert result is None  # Премиум статьи должны пропускаться


@pytest.mark.unit
def test_extract_article_data_with_time_filter():
    """Тестирует извлечение данных с временным фильтром"""
    scraper = FTScraper()
    
    html = """
    <li class="o-teaser-collection__item">
        <div class="o-teaser__content">
            <a href="/content/old-article" class="js-teaser-heading-link">Old Article</a>
            <time title="January 15 2020 10:30 am">Jan 15 2020</time>
        </div>
    </li>
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    article_element = soup.find('li', class_='o-teaser-collection__item')
    
    # Фильтр: только статьи за последний день
    time_filter = lambda date: FTScraper._is_article_recent(date, hours_limit=24)
    
    result = scraper._extract_article_data(article_element, time_filter)
    
    assert result is None  # Старая статья должна быть отфильтрована


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_single_page(mock_playwright):
    """Тестирует скрапинг одной страницы"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    
    scraper = FTScraper()
    scraper.page = page_mock
    
    # Мокаем HTML ответ
    html_content = """
    <html>
        <ul class="o-teaser-collection__list">
            <li class="o-teaser-collection__item">
                <a href="/content/test-1" class="js-teaser-heading-link">Article 1</a>
                <a href="/content/test-1" class="js-teaser-standfirst-link">Content 1</a>
                <time title="January 15 2024 10:30 am">Jan 15 2024</time>
            </li>
        </ul>
    </html>
    """
    
    page_mock.content.return_value = html_content
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()
    
    with patch('asyncio.sleep'):  # Мокаем sleep
        result = await scraper.scrape_single_page(1)
    
    assert len(result) == 1
    assert result[0]['title'] == "Article 1"
    page_mock.goto.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_single_page_no_articles():
    """Тестирует скрапинг страницы без статей"""
    scraper = FTScraper()
    page_mock = AsyncMock()
    scraper.page = page_mock
    
    # HTML без списка статей
    html_content = "<html><body>No articles here</body></html>"
    page_mock.content.return_value = html_content
    
    with patch('asyncio.sleep'):
        result = await scraper.scrape_single_page(1)
    
    assert result == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db(test_db_session):
    """Тестирует сохранение статей в базу данных"""
    articles_data = [
        {
            "url": "https://test.com/article-1",
            "title": "Article 1",
            "content": "Content 1",
            "author": "Author 1",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        },
        {
            "url": "https://test.com/article-2",
            "title": "Article 2",
            "content": "Content 2",
            "author": "Author 2",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        }
    ]
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        
        mock_get_session.return_value = mock_session_generator()
        
        saved_count = await FTScraper.save_articles_to_db(articles_data)
    
    assert saved_count == 2
    
    # Проверяем, что статьи действительно сохранены
    result = await test_db_session.execute(select(Article))
    all_articles = result.scalars().all()
    assert len(all_articles) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db_duplicate(test_db_session):
    """Тестирует обработку дубликатов при сохранении"""
    # Сначала добавляем статью
    article = Article(
        url="https://test.com/duplicate",
        title="Original",
        content="Original content",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        scraped_at=datetime.datetime.now(datetime.timezone.utc)
    )
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Пытаемся добавить дубликат
    articles_data = [
        {
            "url": "https://test.com/duplicate",  # Тот же URL
            "title": "Duplicate",
            "content": "Duplicate content",
            "author": "Author",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        }
    ]
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        
        mock_get_session.return_value = mock_session_generator()
        
        saved_count = await FTScraper.save_articles_to_db(articles_data)
    
    # Дубликат не должен быть сохранен
    assert saved_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db_empty_list():
    """Тестирует сохранение пустого списка статей"""
    result = await FTScraper.save_articles_to_db([])
    assert result == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db_invalid_data(test_db_session):
    """Тестирует обработку невалидных данных"""
    invalid_articles = [
        {
            "title": "No URL",
            "content": "Content without URL"
            # Отсутствует обязательное поле url
        }
    ]
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        async def mock_session_generator():
            yield test_db_session
        
        mock_get_session.return_value = mock_session_generator()
        
        saved_count = await FTScraper.save_articles_to_db(invalid_articles)
    
    assert saved_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_scraping_first_run():
    """Интеграционный тест полного цикла скрапинга при первом запуске"""
    scraper = FTScraper()
    
    # Мокаем все внешние зависимости
    scraper.init_browser = AsyncMock()
    scraper.close_browser = AsyncMock()
    scraper.is_first_run = AsyncMock(return_value=True)
    scraper.scrape_articles_with_pagination = AsyncMock(return_value=[
        {
            "url": "https://test.com/article",
            "title": "Test Article",
            "content": "Test content",
            "author": "Test Author",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        }
    ])
    scraper.save_articles_to_db = AsyncMock(return_value=1)
    
    await scraper.run_scraping()
    
    # Проверяем, что все методы были вызваны
    scraper.init_browser.assert_called_once()
    scraper.is_first_run.assert_called_once()
    scraper.scrape_articles_with_pagination.assert_called_once()
    scraper.save_articles_to_db.assert_called_once()
    scraper.close_browser.assert_called_once()
    
    # Проверяем, что для первого запуска использованы правильные параметры
    args, kwargs = scraper.scrape_articles_with_pagination.call_args
    assert kwargs['max_pages'] == 100


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_scraping_normal_run():
    """Интеграционный тест полного цикла скрапинга при обычном запуске"""
    scraper = FTScraper()
    
    # Мокаем все внешние зависимости
    scraper.init_browser = AsyncMock()
    scraper.close_browser = AsyncMock()
    scraper.is_first_run = AsyncMock(return_value=False)
    scraper.scrape_articles_with_pagination = AsyncMock(return_value=[])
    scraper.save_articles_to_db = AsyncMock(return_value=0)
    
    await scraper.run_scraping()
    
    # Проверяем параметры для обычного запуска
    args, kwargs = scraper.scrape_articles_with_pagination.call_args
    assert kwargs['max_pages'] == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_scraping_with_exception():
    """Тестирует обработку исключений в полном цикле скрапинга"""
    scraper = FTScraper()
    
    scraper.init_browser = AsyncMock(side_effect=Exception("Browser init failed"))
    scraper.close_browser = AsyncMock()
    
    # Не должно выбрасывать исключение
    await scraper.run_scraping()
    
    # Браузер должен быть закрыт даже при ошибке
    scraper.close_browser.assert_called_once()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_scrape_articles_with_pagination():
    """Тестирует скрапинг с пагинацией"""
    scraper = FTScraper()
    
    # Мокаем scrape_single_page чтобы возвращать разные результаты
    call_count = 0
    
    async def mock_scrape_single_page(page_num, time_filter_func=None):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return [{"title": f"Article {call_count}", "published_at": datetime.datetime.now(datetime.timezone.utc)}]
        else:
            return []  # Третья страница пустая
    
    scraper.scrape_single_page = mock_scrape_single_page
    
    with patch('asyncio.sleep'):  # Ускоряем тест
        result = await scraper.scrape_articles_with_pagination(max_pages=5)
    
    assert len(result) == 2  # Две статьи с первых двух страниц
    assert call_count == 5  # Должно попытаться скрапить 3 страницы подряд без результатов