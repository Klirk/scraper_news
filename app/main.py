"""
Главный модуль Financial Times скрапера
"""
import asyncio
import os
from loguru import logger
from dotenv import load_dotenv

from app.scheduler.scheduler import ScrapingScheduler

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logger.add(
    "/app/logs/scraper.log",
    rotation="100 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Глобальная переменная для планировщика
scheduler = None

async def main():
    """Основная функция запуска скрапера"""
    global scheduler

    logger.info("🚀 Starting Financial Times Scraper")
    logger.info("📊 Database URL: {}", os.getenv("DATABASE_URL", "Not configured"))
    logger.info("⏰ Scraper interval: {} hours", os.getenv("SCRAPER_INTERVAL_HOURS", "1"))
    logger.info("📅 Initial days back: {}", os.getenv("INITIAL_DAYS_BACK", "30"))


    try:
        # Создаем и запускаем планировщик
        scheduler = ScrapingScheduler()
        await scheduler.start()

    except KeyboardInterrupt:
        logger.info("👋 Graceful shutdown completed")
    except Exception as e:
        logger.error(f"❌ Critical error: {str(e)}")
        raise


if __name__ == "__main__":
    logger.info("🎯 Application starting...")
    asyncio.run(main())