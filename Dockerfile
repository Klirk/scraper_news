FROM python:3.12-slim

# Установка системных зависимостей для Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libxrandr2 \
    libxcomposite1 \
    libxss1 \
    libgconf-2-4 \
    libxtst6 \
    libxdamage1 \
    libxi6 \
    libxfixes3 \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Установка Playwright браузеров (от root пользователя)
RUN playwright install-deps chromium
RUN playwright install chromium

# Копирование кода приложения
COPY . .

# Создание директорий для логов и данных
RUN mkdir -p /app/logs /app/data

# Создание пользователя для безопасности
RUN useradd --create-home --shell /bin/bash scraper && \
    chown -R scraper:scraper /app && \
    chmod -R 755 /app/logs /app/data

# Настройка переменных окружения для Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/home/scraper/.cache/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Переключаемся на пользователя scraper и устанавливаем браузеры от его имени
USER scraper

# Установка браузеров от имени пользователя scraper
RUN playwright install chromium

# Открытие порта
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "-m", "app.main"]