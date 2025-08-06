#!/usr/bin/env python3
"""
Быстрый запуск FastAPI сервера для разработки
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Автоперезагрузка при изменении файлов
        log_level="info"
    )