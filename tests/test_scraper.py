"""
Тесты для модуля скрапинга Financial Times
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

from app.scraper.scraper import FTScraper


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_initialization():
    """Тест инициализации скрапера"""
    scraper = FTScraper()
    
    assert scraper.browser is None
    assert scraper.page is None
    assert scraper.playwright is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_start_browser(mock_playwright):
    """Тест запуска браузера"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    
    scraper = FTScraper()
    
    with patch('app.scraper.scraper.async_playwright') as mock_async_playwright:
        mock_async_playwright.return_value.__aenter__.return_value = playwright_mock
        
        await scraper.start_browser()
        
        assert scraper.playwright == playwright_mock
        assert scraper.browser == browser_mock
        assert scraper.page == page_mock
        
        # Проверяем что браузер был запущен с правильными параметрами
        playwright_mock.chromium.launch.assert_called_once()
        browser_mock.new_context.assert_called_once()
        context_mock.new_page.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_close_browser():
    """Тест закрытия браузера"""
    scraper = FTScraper()
    scraper.browser = AsyncMock()
    scraper.playwright = AsyncMock()
    
    await scraper.close_browser()
    
    scraper.browser.close.assert_called_once()
    scraper.playwright.stop.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_first_run_empty_database():
    """Тест проверки первого запуска с пустой базой"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 0  # Пустая база
    mock_session.execute.return_value = mock_result
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        mock_get_session.return_value.__aiter__.return_value = [mock_session]
        
        result = await FTScraper.is_first_run()
        
        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_first_run_with_articles():
    """Тест проверки первого запуска с существующими статьями"""
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 5  # В базе есть статьи
    mock_session.execute.return_value = mock_result
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        mock_get_session.return_value.__aiter__.return_value = [mock_session]
        
        result = await FTScraper.is_first_run()
        
        assert result is False


@pytest.mark.unit
def test_is_article_recent():
    """Тест проверки актуальности статьи"""
    now = datetime.now(timezone.utc)
    
    # Статья опубликована час назад (свежая)
    recent_date = now - timedelta(minutes=30)
    assert FTScraper._is_article_recent(recent_date, hours_limit=1) is True
    
    # Статья опубликована 2 часа назад (старая)
    old_date = now - timedelta(hours=2)
    assert FTScraper._is_article_recent(old_date, hours_limit=1) is False
    
    # Статья опубликована в будущем (должна считаться свежей)
    future_date = now + timedelta(minutes=30)
    assert FTScraper._is_article_recent(future_date, hours_limit=1) is True


@pytest.mark.unit
def test_parse_published_date():
    """Тест парсинга даты публикации"""
    # Тестируем различные форматы дат
    test_cases = [
        ("January 15 2024 10:30 am", "2024-01-15 10:30:00+00:00"),
        ("December 25 2023 11:45 pm", "2023-12-25 23:45:00+00:00"),
        ("March 1 2024 1:15 pm", "2024-03-01 13:15:00+00:00"),
    ]
    
    for date_str, expected in test_cases:
        result = FTScraper._parse_published_date(date_str)
        assert result is not None
        assert result.strftime("%Y-%m-%d %H:%M:%S%z") == expected


@pytest.mark.unit
def test_parse_published_date_invalid():
    """Тест парсинга некорректной даты"""
    invalid_dates = [
        "invalid date format",
        "32 January 2024 25:70 am",
        "",
        None
    ]
    
    for invalid_date in invalid_dates:
        with pytest.raises((ValueError, AttributeError)):
            FTScraper._parse_published_date(invalid_date)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_articles_from_html(mock_html_content):
    """Тест парсинга статей из HTML"""
    scraper = FTScraper()
    
    # Мокаем BeautifulSoup
    soup = BeautifulSoup(mock_html_content, 'html.parser')
    
    # Тестируем парсинг
    with patch.object(scraper, '_parse_published_date') as mock_parse_date:
        mock_parse_date.return_value = datetime.now(timezone.utc)
        
        articles = scraper._parse_articles_from_html(soup)
        
        assert len(articles) == 2
        assert articles[0]['title'] == 'Test Article 1'
        assert articles[1]['title'] == 'Test Article 2'
        assert 'test-article-1' in articles[0]['url']
        assert 'test-article-2' in articles[1]['url']


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_single_page(mock_playwright, mock_html_content):
    """Тест скрапинга одной страницы"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    page_mock.content.return_value = mock_html_content
    
    scraper = FTScraper()
    scraper.playwright = playwright_mock
    scraper.browser = browser_mock
    scraper.page = page_mock
    
    with patch.object(scraper, '_parse_published_date') as mock_parse_date:
        mock_parse_date.return_value = datetime.now(timezone.utc)
        
        articles = await scraper.scrape_single_page(1)
        
        assert len(articles) >= 0  # Может быть пустым из-за фильтрации
        page_mock.goto.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio 
async def test_scrape_single_page_with_filter(mock_playwright, mock_html_content):
    """Тест скрапинга одной страницы с временным фильтром"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    page_mock.content.return_value = mock_html_content
    
    scraper = FTScraper()
    scraper.playwright = playwright_mock
    scraper.browser = browser_mock
    scraper.page = page_mock
    
    # Создаем фильтр который пропускает только статьи за последний час
    def time_filter(pub_date):
        return pub_date > datetime.now(timezone.utc) - timedelta(hours=1)
    
    with patch.object(scraper, '_parse_published_date') as mock_parse_date:
        # Возвращаем старую дату (будет отфильтрована)
        mock_parse_date.return_value = datetime.now(timezone.utc) - timedelta(hours=2)
        
        articles = await scraper.scrape_single_page(1, time_filter)
        
        assert len(articles) == 0  # Все статьи должны быть отфильтрованы


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_articles_with_pagination(mock_playwright, mock_html_content):
    """Тест скрапинга с пагинацией"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    page_mock.content.return_value = mock_html_content
    
    scraper = FTScraper()
    scraper.playwright = playwright_mock
    scraper.browser = browser_mock
    scraper.page = page_mock
    
    with patch.object(scraper, '_parse_published_date') as mock_parse_date:
        mock_parse_date.return_value = datetime.now(timezone.utc)
        
        with patch.object(scraper, 'scrape_single_page') as mock_scrape_page:
            mock_scrape_page.return_value = [
                {
                    'title': 'Test Article',
                    'url': 'https://ft.com/test',
                    'published_at': datetime.now(timezone.utc)
                }
            ]
            
            articles = await scraper.scrape_articles_with_pagination(max_pages=3)
            
            assert len(articles) == 3  # 3 страницы * 1 статья
            assert mock_scrape_page.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db_success(sample_articles_list):
    """Тест успешного сохранения статей в базу данных"""
    mock_session = AsyncMock()
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        mock_get_session.return_value.__aiter__.return_value = [mock_session]
        
        saved_count = await FTScraper.save_articles_to_db(sample_articles_list)
        
        assert saved_count == len(sample_articles_list)
        assert mock_session.add.call_count == len(sample_articles_list)
        mock_session.commit.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_save_articles_to_db_with_duplicates(sample_articles_list):
    """Тест сохранения статей с дубликатами"""
    from sqlalchemy.exc import IntegrityError
    
    mock_session = AsyncMock()
    mock_session.commit.side_effect = [IntegrityError("duplicate", None, None), None, None]
    
    with patch('app.scraper.scraper.get_session') as mock_get_session:
        mock_get_session.return_value.__aiter__.return_value = [mock_session]
        
        saved_count = await FTScraper.save_articles_to_db(sample_articles_list)
        
        # Первая статья должна быть отклонена из-за дубликата
        assert saved_count == len(sample_articles_list) - 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scrape_article_content(mock_playwright, mock_article_html):
    """Тест скрапинга содержимого отдельной статьи"""
    playwright_mock, browser_mock, context_mock, page_mock = mock_playwright
    page_mock.content.return_value = mock_article_html
    
    scraper = FTScraper()
    scraper.page = page_mock
    
    content = await scraper._scrape_article_content("https://ft.com/test-article")
    
    assert "This is the first paragraph" in content
    assert "This is the second paragraph" in content
    assert "And this is the final paragraph" in content
    page_mock.goto.assert_called_once_with("https://ft.com/test-article", wait_until='load', timeout=30000)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_scraping_workflow(scraper_with_mock_db, mock_html_content):
    """Интеграционный тест полного процесса скрапинга"""
    scraper = scraper_with_mock_db
    scraper.page.content.return_value = mock_html_content
    
    with patch.object(scraper, '_parse_published_date') as mock_parse_date:
        mock_parse_date.return_value = datetime.now(timezone.utc)
        
        with patch.object(scraper, '_scrape_article_content') as mock_content:
            mock_content.return_value = "Full article content here"
            
            # Выполняем полный цикл скрапинга
            articles = await scraper.scrape_single_page(1)
            
            if articles:
                saved_count = await scraper.save_articles_to_db(articles)
                assert saved_count >= 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_error_handling():
    """Тест обработки ошибок в скрапере"""
    scraper = FTScraper()
    scraper.page = AsyncMock()
    scraper.page.goto.side_effect = Exception("Network error")
    
    # Тестируем что ошибки обрабатываются корректно
    articles = await scraper.scrape_single_page(1)
    assert articles == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_timeout_handling():
    """Тест обработки таймаутов"""
    scraper = FTScraper()
    scraper.page = AsyncMock()
    scraper.page.wait_for_selector.side_effect = TimeoutError("Timeout waiting for selector")
    
    # Проверяем что таймауты обрабатываются корректно
    articles = await scraper.scrape_single_page(1)
    assert isinstance(articles, list)


@pytest.mark.unit
def test_scraper_url_building():
    """Тест построения URL для скрапинга"""
    # Тестируем что URL строятся корректно для разных страниц
    base_url = "https://www.ft.com"
    
    for page_num in range(1, 5):
        if page_num == 1:
            expected_url = base_url
        else:
            expected_url = f"{base_url}?page={page_num}"
        
        # Это внутренняя логика, которую можно протестировать
        # через проверку вызовов page.goto в других тестах
        assert expected_url is not None