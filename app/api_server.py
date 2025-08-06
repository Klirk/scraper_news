"""
Запуск только FastAPI сервера без планировщика
Полезно для разработки или когда планировщик запущен отдельно
"""
import uvicorn
from loguru import logger

from app.api.app import app


def main():
    """Запуск FastAPI сервера"""
    logger.info("🌐 Запуск FastAPI сервера (только API)...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
        reload=False  # Установить True для разработки
    )


if __name__ == "__main__":
    main()