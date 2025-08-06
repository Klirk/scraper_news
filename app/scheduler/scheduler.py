"""
Планировщик задач для скрапинга Financial Times
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.scraper.scraper import FTScraper


class ScrapingScheduler:
    """Планировщик для автоматического скрапинга новостей"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scraper = FTScraper()

    async def initial_scrape_job(self):
        """Задача первоначального скрапинга (30 дней)"""
        try:
            logger.info("🔄 Запуск задачи первоначального скрапинга...")
            await self.scraper.run_initial_scraping()
            logger.info("✅ Задача первоначального скрапинга завершена")
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче первоначального скрапинга: {e}")

    async def hourly_scrape_job(self):
        """Задача почасового скрапинга"""
        try:
            logger.info("⏰ Запуск почасовой задачи скрапинга...")
            await self.scraper.run_hourly_scraping()
            logger.info("✅ Почасовая задача скрапинга завершена")
        except Exception as e:
            logger.error(f"❌ Ошибка в почасовой задаче скрапинга: {e}")

    async def adaptive_scrape_job(self):
        """Адаптивная задача скрапинга (автоматически определяет режим)"""
        try:
            logger.info("🤖 Запуск адаптивной задачи скрапинга...")
            await self.scraper.run_scraping()
            logger.info("✅ Адаптивная задача скрапинга завершена")
        except Exception as e:
            logger.error(f"❌ Ошибка в адаптивной задаче скрапинга: {e}")

    async def start(self):
        """Запуск планировщика"""
        try:
            logger.info("⚡ Запуск планировщика задач...")

            # Проверяем, первый ли это запуск
            is_first = await self.scraper.is_first_run()

            if is_first:
                logger.info("🆕 Первый запуск - начинаем сбор за 30 дней...")
                # Запускаем первоначальный скрапинг
                await self.initial_scrape_job()

                # Настраиваем почасовой режим для будущих запусков
                logger.info("⏰ Настройка почасового режима для будущих запусков...")
                self.scheduler.add_job(
                    self.hourly_scrape_job,
                    trigger=IntervalTrigger(hours=1),
                    id='hourly_scraping_job',
                    name='FT Hourly Scraping',
                    replace_existing=True
                )

                # Запускаем планировщик
                self.scheduler.start()
                logger.info("✅ Планировщик запущен в почасовом режиме (каждый час)")

            else:
                logger.info("🔄 Обычный запуск - используем адаптивный режим...")
                # Запускаем адаптивный скрапинг сразу
                await self.adaptive_scrape_job()

                # Настраиваем почасовой режим
                self.scheduler.add_job(
                    self.hourly_scrape_job,
                    trigger=IntervalTrigger(hours=1),
                    id='hourly_scraping_job',
                    name='FT Hourly Scraping',
                    replace_existing=True
                )

                # Запускаем планировщик
                self.scheduler.start()
                logger.info("✅ Планировщик запущен в почасовом режиме (каждый час)")

            # Бесконечный цикл для работы планировщика
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки планировщика...")
            await self.stop()
        except Exception as e:
            logger.error(f"❌ Ошибка планировщика: {e}")
            await self.stop()

    async def start_manual_mode(self):
        """Запуск в ручном режиме без планировщика"""
        try:
            logger.info("🔧 Запуск в ручном режиме...")
            await self.adaptive_scrape_job()
        except Exception as e:
            logger.error(f"❌ Ошибка ручного режима: {e}")

    async def stop(self):
        """Остановка планировщика"""
        try:
            logger.info("🛑 Остановка планировщика...")
            if self.scheduler.running:
                self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки планировщика: {e}")
