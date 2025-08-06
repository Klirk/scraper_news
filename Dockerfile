FROM python:3.12-slim

# Установка системных зависимостей для Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .


# Настройка переменных окружения для Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/home/scraper/.cache/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Установка браузеров от имени пользователя scraper
RUN playwright install-deps chromium
RUN playwright install chromium

# Открытие порта
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "-m", "app.main"]