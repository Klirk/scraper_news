"""
Основное FastAPI приложение для Financial Times скрапера
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.routes import articles_router, system_router
from app.api.models import ErrorResponse
from app.db.database import init_db, close_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("🚀 Запуск FastAPI приложения...")
    try:
        # Инициализация базы данных
        logger.info("📊 Инициализация базы данных...")
        await init_db()
        logger.info("✅ База данных инициализирована")

        yield

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🔌 Закрытие подключений к базе данных...")
        await close_db()
        logger.info("✅ FastAPI приложение остановлено")


# Создание экземпляра FastAPI
app = FastAPI(
    title="Financial Times Scraper API",
    description="""
    REST API для Financial Times скрапера
    
    ## Возможности
    
    * **Статьи** - получение статей с пагинацией и фильтрацией
    * **Система** - мониторинг статуса и статистики
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(articles_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


# Глобальная обработка ошибок
@app.exception_handler(Exception)
async def global_exception_handler(_request, exc):
    """Глобальная обработка неожиданных ошибок"""
    logger.error(f"Неожиданная ошибка: {exc}")

    # Показываем детали ошибки только в режиме отладки
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Внутренняя ошибка сервера",
            detail=str(exc) if debug_mode else None
        ).model_dump()
    )


# Базовые endpoints
@app.get("/", tags=["Root"])
async def root():
    """Корневой endpoint"""
    return {
        "message": "Financial Times Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "api_base": "/api/v1"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-20T10:00:00Z"
    }


# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request, call_next):
    """Логирование HTTP запросов"""
    import time

    start_time = time.time()
    logger.info(f"🌐 {request.method} {request.url}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f"✅ {request.method} {request.url} - {response.status_code} ({process_time:.3f}s)"
    )

    return response
