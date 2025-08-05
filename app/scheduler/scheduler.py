"""
Планировщик задач для скрапинга
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.scraper.scraper import FTScraper, ArticleProcessor
from app.db.database import engine
from app.models.models import Base


class ScrapingScheduler:
    """Планировщик для автоматического скрапинга"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scraper = None
        self.processor = ArticleProcessor()
        self.is_initial_run = True

        # Настройки из переменных окружения
        self.interval_hours = int(os.getenv('SCRAPER_INTERVAL_HOURS', '1'))
        self.initial_days_back = int(os.getenv('INITIAL_DAYS_BACK', '30'))
        self.max_concurrent = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
        self.request_delay = int(os.getenv('REQUEST_DELAY', '2'))

    async def init_database(self):
        """Инициализация базы данных - создание таблиц"""
        logger.info("🗄️ Initializing database tables...")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.success("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Error creating database tables: {str(e)}")
            raise

    async def run_scraping_job(self, days_back: Optional[int] = None):
        """
        Основная задача скрапинга

        Args:
            days_back: Количество дней для поиска статей (None = использовать стандартное)
        """
        start_time = datetime.utcnow()

        if days_back is None:
            days_back = self.initial_days_back if self.is_initial_run else 1

        run_type = "initial" if self.is_initial_run else "hourly"

        logger.info(f"🚀 Starting {run_type} scraping job (last {days_back} days)")

        stats = {
            'found': 0,
            'scraped': 0,
            'saved': 0,
            'skipped': 0,
            'errors': 0
        }

        try:
            async with FTScraper() as scraper:
                # Получаем ссылки на статьи
                article_links = await scraper.get_article_links(days_back=days_back)
                stats['found'] = len(article_links)

                if not article_links:
                    logger.warning("⚠️ No articles found")
                    return stats

                # Создаем семафор для ограничения конкурентных запросов
                semaphore = asyncio.Semaphore(self.max_concurrent)

                # Функция для обработки одной статьи
                async def process_article(article_info):
                    async with semaphore:
                        try:
                            # Задержка между запросами
                            await asyncio.sleep(self.request_delay)

                            # Скрапим статью
                            article_data = await scraper.scrape_article(article_info['url'])

                            if article_data is None:
                                stats['skipped'] += 1
                                return

                            stats['scraped'] += 1

                            # Сохраняем в базу
                            saved = await self.processor.save_article(article_data)
                            if saved:
                                stats['saved'] += 1
                            else:
                                stats['skipped'] += 1

                        except Exception as e:
                            logger.error(f"❌ Error processing article {article_info['url']}: {str(e)}")
                            stats['errors'] += 1

                # Обрабатываем статьи параллельно
                tasks = [process_article(article_info) for article_info in article_links]
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"❌ Critical error in scraping job: {str(e)}")
            stats['errors'] += 1
            raise

        finally:
            # Логируем статистику
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"📊 Scraping completed in {duration:.1f}s: "
                f"Found: {stats['found']}, "
                f"Scraped: {stats['scraped']}, "
                f"Saved: {stats['saved']}, "
                f"Skipped: {stats['skipped']}, "
                f"Errors: {stats['errors']}"
            )

            # После первого запуска переключаемся на обычный режим
            if self.is_initial_run:
                self.is_initial_run = False
                logger.info("🔄 Switched to hourly scraping mode")

        return stats

    async def start(self):
        """Запуск планировщика"""
        try:
            # Инициализируем базу данных
            await self.init_database()

            # Запускаем первый скрапинг сразу
            logger.info("🎯 Running initial scraping...")
            await self.run_scraping_job()

            # Настраиваем периодические задачи
            self.scheduler.add_job(
                self.run_scraping_job,
                trigger=IntervalTrigger(hours=self.interval_hours),
                id='hourly_scraping',
                name='Hourly FT Scraping',
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300  # 5 минут
            )

            # Добавляем задачу очистки логов (опционально)
            self.scheduler.add_job(
                self._cleanup_logs,
                trigger=CronTrigger(hour=3),  # Каждый день в 3 утра
                id='cleanup_logs',
                name='Daily log cleanup'
            )

            # Запускаем планировщик
            self.scheduler.start()
            logger.success(f"⏰ Scheduler started with {self.interval_hours}h interval")

            # Поддерживаем работу
            try:
                while True:
                    await asyncio.sleep(60)  # Проверяем каждую минуту

            except KeyboardInterrupt:
                logger.info("⏹️ Received shutdown signal")

        except Exception as e:
            logger.error(f"❌ Error starting scheduler: {str(e)}")
            raise

        finally:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("🛑 Scheduler stopped")

    async def _cleanup_logs(self):
        """Очистка старых логов (опционально)"""
        logger.info("🧹 Running daily log cleanup...")
        # Здесь можно добавить логику очистки старых логов
        # Например, удаление файлов логов старше 30 дней

    def stop(self):
        """Остановка планировщика"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("🛑 Scheduler stopped manually")


# Функция для ручного запуска скрапинга
async def run_manual_scraping(days_back: int = 1):
    """
    Ручной запуск скрапинга для тестирования

    Args:
        days_back: Количество дней назад
    """
    scheduler = ScrapingScheduler()
    await scheduler.init_database()
    return await scheduler.run_scraping_job(days_back=days_back)