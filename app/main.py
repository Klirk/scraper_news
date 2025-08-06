"""
Главный модуль Financial Times скрапера с FastAPI
"""
import asyncio
import uvicorn
from loguru import logger
from dotenv import load_dotenv

from app.scheduler.scheduler import ScrapingScheduler
from app.db.database import init_db, close_db
from app.api.app import app as fastapi_app

# Загрузка переменных окружения
load_dotenv()

from pathlib import Path

# Создаем директорию для логов если её нет
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Путь к файлу логов
log_file = log_dir / "scraper.log"

logger.add(
    str(log_file),
    rotation="100 MB",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)


async def run_scheduler():
    """Запуск планировщика скрапинга"""
    try:
        logger.info("⏰ Запуск планировщика...")
        scheduler = ScrapingScheduler()
        await scheduler.start()
    except Exception as e:
        logger.error(f"❌ Ошибка планировщика: {e}")
        raise


async def run_fastapi():
    """Запуск FastAPI сервера"""
    try:
        logger.info("🌐 Запуск FastAPI сервера...")
        config = uvicorn.Config(
            app=fastapi_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.error(f"❌ Ошибка FastAPI сервера: {e}")
        raise


async def main():
    """Главная функция запуска приложения"""
    try:
        logger.info("🚀 Запуск Financial Times скрапера с FastAPI...")
        
        # Инициализация базы данных
        logger.info("📊 Инициализация базы данных...")
        await init_db()
        
        logger.info("🔥 Запуск сервисов параллельно...")
        
        # Запуск FastAPI и планировщика параллельно
        await asyncio.gather(
            run_fastapi(),
            run_scheduler(),
            return_exceptions=True
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        # Закрытие подключений к базе данных
        logger.info("🔌 Закрытие подключений к базе данных...")
        await close_db()
        logger.info("✅ Приложение завершено")


if __name__ == "__main__":
    # Запуск приложения
    asyncio.run(main())