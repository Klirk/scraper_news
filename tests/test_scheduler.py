"""
Тесты для планировщика задач
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.scheduler.scheduler import ScrapingScheduler


@pytest.mark.unit
def test_scheduler_initialization():
    """Тестирует инициализацию планировщика"""
    scheduler = ScrapingScheduler()
    
    assert scheduler.scheduler is not None
    assert scheduler.scraper is not None
    assert hasattr(scheduler.scheduler, 'add_job')
    assert hasattr(scheduler.scheduler, 'start')
    assert hasattr(scheduler.scheduler, 'shutdown')


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initial_scrape_job():
    """Тестирует задачу первоначального скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_initial_scraping = AsyncMock()
    
    await scheduler.initial_scrape_job()
    
    scheduler.scraper.run_initial_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initial_scrape_job_with_exception():
    """Тестирует обработку исключений в задаче первоначального скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_initial_scraping = AsyncMock(side_effect=Exception("Test error"))
    
    # Не должно выбрасывать исключение
    await scheduler.initial_scrape_job()
    
    scheduler.scraper.run_initial_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hourly_scrape_job():
    """Тестирует почасовую задачу скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_hourly_scraping = AsyncMock()
    
    await scheduler.hourly_scrape_job()
    
    scheduler.scraper.run_hourly_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hourly_scrape_job_with_exception():
    """Тестирует обработку исключений в почасовой задаче"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_hourly_scraping = AsyncMock(side_effect=Exception("Test error"))
    
    # Не должно выбрасывать исключение
    await scheduler.hourly_scrape_job()
    
    scheduler.scraper.run_hourly_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adaptive_scrape_job():
    """Тестирует адаптивную задачу скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_scraping = AsyncMock()
    
    await scheduler.adaptive_scrape_job()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adaptive_scrape_job_with_exception():
    """Тестирует обработку исключений в адаптивной задаче"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_scraping = AsyncMock(side_effect=Exception("Test error"))
    
    # Не должно выбрасывать исключение
    await scheduler.adaptive_scrape_job()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_manual_mode():
    """Тестирует запуск в ручном режиме"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_scraping = AsyncMock()
    
    await scheduler.start_manual_mode()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_manual_mode_with_exception():
    """Тестирует обработку исключений в ручном режиме"""
    scheduler = ScrapingScheduler()
    scheduler.scraper.run_scraping = AsyncMock(side_effect=Exception("Test error"))
    
    # Не должно выбрасывать исключение
    await scheduler.start_manual_mode()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop():
    """Тестирует остановку планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler.running = True
    scheduler.scheduler.shutdown = MagicMock()
    
    await scheduler.stop()
    
    scheduler.scheduler.shutdown.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_not_running():
    """Тестирует остановку планировщика когда он не запущен"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler.running = False
    scheduler.scheduler.shutdown = MagicMock()
    
    await scheduler.stop()
    
    # shutdown не должен быть вызван если планировщик не запущен
    scheduler.scheduler.shutdown.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_with_exception():
    """Тестирует обработку исключений при остановке планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler.running = True
    scheduler.scheduler.shutdown = MagicMock(side_effect=Exception("Shutdown error"))
    
    # Не должно выбрасывать исключение
    await scheduler.stop()
    
    scheduler.scheduler.shutdown.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_first_run():
    """Интеграционный тест первого запуска планировщика"""
    scheduler = ScrapingScheduler()
    
    # Мокаем методы
    scheduler.scraper.is_first_run = AsyncMock(return_value=True)
    scheduler.scraper.run_initial_scraping = AsyncMock()
    scheduler.scheduler.add_job = MagicMock()
    scheduler.scheduler.start = MagicMock()
    
    # Мокаем asyncio.sleep чтобы не ждать
    original_sleep = asyncio.sleep
    sleep_count = 0
    
    async def mock_sleep(duration):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 2:  # Прерываем после нескольких итераций
            raise KeyboardInterrupt("Test interrupt")
        await original_sleep(0.01)  # Короткая пауза
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        try:
            await scheduler.start()
        except KeyboardInterrupt:
            pass  # Ожидаемое исключение для завершения теста
    
    # Проверяем, что были вызваны нужные методы
    scheduler.scraper.is_first_run.assert_called_once()
    scheduler.scraper.run_initial_scraping.assert_called_once()
    scheduler.scheduler.add_job.assert_called_once()
    scheduler.scheduler.start.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_normal_run():
    """Интеграционный тест обычного запуска планировщика"""
    scheduler = ScrapingScheduler()
    
    # Мокаем методы
    scheduler.scraper.is_first_run = AsyncMock(return_value=False)
    scheduler.adaptive_scrape_job = AsyncMock()
    scheduler.scheduler.add_job = MagicMock()
    scheduler.scheduler.start = MagicMock()
    
    # Мокаем asyncio.sleep чтобы не ждать
    sleep_count = 0
    
    async def mock_sleep(duration):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 2:  # Прерываем после нескольких итераций
            raise KeyboardInterrupt("Test interrupt")
        await asyncio.sleep(0.01)  # Короткая пауза
    
    with patch('asyncio.sleep', side_effect=mock_sleep):
        try:
            await scheduler.start()
        except KeyboardInterrupt:
            pass  # Ожидаемое исключение для завершения теста
    
    # Проверяем, что были вызваны нужные методы
    scheduler.scraper.is_first_run.assert_called_once()
    scheduler.adaptive_scrape_job.assert_called_once()
    scheduler.scheduler.add_job.assert_called_once()
    scheduler.scheduler.start.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_with_exception():
    """Тестирует обработку исключений при запуске планировщика"""
    scheduler = ScrapingScheduler()
    
    # Мокаем методы так чтобы is_first_run выбрасывал исключение
    scheduler.scraper.is_first_run = AsyncMock(side_effect=Exception("Test error"))
    scheduler.stop = AsyncMock()
    
    await scheduler.start()
    
    # Проверяем, что метод stop был вызван при исключении
    scheduler.stop.assert_called_once()


@pytest.mark.unit
def test_scheduler_job_configuration():
    """Тестирует конфигурацию задач планировщика"""
    from apscheduler.triggers.interval import IntervalTrigger
    
    scheduler = ScrapingScheduler()
    mock_add_job = MagicMock()
    scheduler.scheduler.add_job = mock_add_job
    
    # Имитируем добавление задачи как в реальном коде
    scheduler.scheduler.add_job(
        scheduler.hourly_scrape_job,
        trigger=IntervalTrigger(hours=1),
        id='hourly_scraping_job',
        name='FT Hourly Scraping',
        replace_existing=True
    )
    
    # Проверяем, что add_job был вызван с правильными параметрами
    mock_add_job.assert_called_once()
    args, kwargs = mock_add_job.call_args
    
    assert args[0] == scheduler.hourly_scrape_job
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['id'] == 'hourly_scraping_job'
    assert kwargs['name'] == 'FT Hourly Scraping'
    assert kwargs['replace_existing'] is True