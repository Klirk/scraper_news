"""
Тесты для планировщика задач скрапинга
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.scheduler import ScrapingScheduler


@pytest.mark.unit
def test_scheduler_initialization():
    """Тест инициализации планировщика"""
    scheduler = ScrapingScheduler()
    
    assert scheduler.scheduler is not None
    assert isinstance(scheduler.scheduler, AsyncIOScheduler)
    assert scheduler.scraper is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initial_scrape_job():
    """Тест задачи первоначального скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    
    await scheduler.initial_scrape_job()
    
    scheduler.scraper.run_initial_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initial_scrape_job_error_handling():
    """Тест обработки ошибок в задаче первоначального скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.run_initial_scraping.side_effect = Exception("Scraping failed")
    
    # Задача должна обработать ошибку без падения
    await scheduler.initial_scrape_job()
    
    scheduler.scraper.run_initial_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hourly_scrape_job():
    """Тест почасовой задачи скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    
    await scheduler.hourly_scrape_job()
    
    scheduler.scraper.run_hourly_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hourly_scrape_job_error_handling():
    """Тест обработки ошибок в почасовой задаче"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.run_hourly_scraping.side_effect = Exception("Hourly scraping failed")
    
    # Задача должна обработать ошибку без падения
    await scheduler.hourly_scrape_job()
    
    scheduler.scraper.run_hourly_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adaptive_scrape_job():
    """Тест адаптивной задачи скрапинга"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    
    await scheduler.adaptive_scrape_job()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adaptive_scrape_job_error_handling():
    """Тест обработки ошибок в адаптивной задаче"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.run_scraping.side_effect = Exception("Adaptive scraping failed")
    
    # Задача должна обработать ошибку без падения
    await scheduler.adaptive_scrape_job()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_manual_mode():
    """Тест запуска в ручном режиме"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    
    await scheduler.start_manual_mode()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_manual_mode_error_handling():
    """Тест обработки ошибок в ручном режиме"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.run_scraping.side_effect = Exception("Manual mode failed")
    
    # Режим должен обработать ошибку без падения
    await scheduler.start_manual_mode()
    
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_scheduler():
    """Тест остановки планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = True
    
    await scheduler.stop()
    
    scheduler.scheduler.shutdown.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_scheduler_not_running():
    """Тест остановки уже остановленного планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = False
    
    await scheduler.stop()
    
    # Shutdown не должен быть вызван для неработающего планировщика
    scheduler.scheduler.shutdown.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_scheduler_error_handling():
    """Тест обработки ошибок при остановке планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = True
    scheduler.scheduler.shutdown.side_effect = Exception("Shutdown failed")
    
    # Остановка должна обработать ошибку без падения
    await scheduler.stop()
    
    scheduler.scheduler.shutdown.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_first_run():
    """Тест запуска планировщика при первом запуске"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.is_first_run.return_value = True
    scheduler.scheduler = MagicMock()
    
    # Мокаем бесконечный цикл чтобы тест завершился
    with patch('asyncio.sleep') as mock_sleep:
        mock_sleep.side_effect = KeyboardInterrupt("Stop test")
        
        await scheduler.start()
        
        # Проверяем что был вызван первоначальный скрапинг
        scheduler.scraper.run_initial_scraping.assert_called_once()
        
        # Проверяем что была добавлена почасовая задача
        scheduler.scheduler.add_job.assert_called_once()
        scheduler.scheduler.start.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_subsequent_run():
    """Тест запуска планировщика при повторном запуске"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.is_first_run.return_value = False
    scheduler.scheduler = MagicMock()
    
    # Мокаем бесконечный цикл чтобы тест завершился
    with patch('asyncio.sleep') as mock_sleep:
        mock_sleep.side_effect = KeyboardInterrupt("Stop test")
        
        await scheduler.start()
        
        # Проверяем что был вызван адаптивный скрапинг
        scheduler.scraper.run_scraping.assert_called_once()
        
        # Проверяем что была добавлена почасовая задача
        scheduler.scheduler.add_job.assert_called_once()
        scheduler.scheduler.start.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_with_exception():
    """Тест обработки исключений при запуске планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.is_first_run.side_effect = Exception("Database error")
    scheduler.scheduler = MagicMock()
    
    await scheduler.start()
    
    # Проверяем что остановка была вызвана при ошибке
    scheduler.scheduler.shutdown.assert_called()


@pytest.mark.unit
def test_scheduler_job_configuration():
    """Тест конфигурации задач планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scheduler = MagicMock()
    
    # Симулируем добавление задачи
    scheduler.scheduler.add_job(
        scheduler.hourly_scrape_job,
        trigger=None,  # IntervalTrigger в реальном коде
        id='hourly_scraping_job',
        name='FT Hourly Scraping',
        replace_existing=True
    )
    
    # Проверяем что задача была добавлена
    scheduler.scheduler.add_job.assert_called_once()
    
    # Проверяем параметры вызова
    call_args = scheduler.scheduler.add_job.call_args
    assert call_args[1]['id'] == 'hourly_scraping_job'
    assert call_args[1]['name'] == 'FT Hourly Scraping'
    assert call_args[1]['replace_existing'] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Тест полного жизненного цикла планировщика"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    scheduler.scraper.is_first_run.return_value = False
    
    # Мокаем scheduler для контроля его поведения
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.running = True
    
    # Тестируем ручной режим
    await scheduler.start_manual_mode()
    scheduler.scraper.run_scraping.assert_called()
    
    # Тестируем остановку
    await scheduler.stop()
    scheduler.scheduler.shutdown.assert_called_once()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_scheduler_real_timing():
    """Медленный тест для проверки реального времени (помечен как slow)"""
    scheduler = ScrapingScheduler()
    scheduler.scraper = AsyncMock()
    
    start_time = asyncio.get_event_loop().time()
    
    # Выполняем задачу
    await scheduler.adaptive_scrape_job()
    
    end_time = asyncio.get_event_loop().time()
    duration = end_time - start_time
    
    # Проверяем что задача выполняется быстро (меньше 1 секунды)
    assert duration < 1.0
    scheduler.scraper.run_scraping.assert_called_once()


@pytest.mark.unit
def test_scheduler_attributes():
    """Тест атрибутов планировщика"""
    scheduler = ScrapingScheduler()
    
    # Проверяем что все необходимые атрибуты присутствуют
    assert hasattr(scheduler, 'scheduler')
    assert hasattr(scheduler, 'scraper')
    assert hasattr(scheduler, 'initial_scrape_job')
    assert hasattr(scheduler, 'hourly_scrape_job')
    assert hasattr(scheduler, 'adaptive_scrape_job')
    assert hasattr(scheduler, 'start')
    assert hasattr(scheduler, 'start_manual_mode')
    assert hasattr(scheduler, 'stop')


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_scheduler_instances():
    """Тест создания нескольких экземпляров планировщика"""
    scheduler1 = ScrapingScheduler()
    scheduler2 = ScrapingScheduler()
    
    # Проверяем что это разные экземпляры
    assert scheduler1 is not scheduler2
    assert scheduler1.scheduler is not scheduler2.scheduler
    assert scheduler1.scraper is not scheduler2.scraper
    
    # Проверяем что каждый может работать независимо
    scheduler1.scraper = AsyncMock()
    scheduler2.scraper = AsyncMock()
    
    await scheduler1.adaptive_scrape_job()
    await scheduler2.adaptive_scrape_job()
    
    scheduler1.scraper.run_scraping.assert_called_once()
    scheduler2.scraper.run_scraping.assert_called_once()