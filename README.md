# Financial Times Scraper API

🗞️ **Автоматичний скрапер новин Financial Times з REST API інтерфейсом**

Цей проект автоматично збирає статті з Financial Times та надає зручний REST API для роботи з ними.

## ✨ Особливості

- 🤖 **Автоматичний скрапинг** - планувальник задач для регулярного збору новин
- 🚀 **FastAPI** - сучасний REST API з автоматичною документацією
- 📊 **PostgreSQL** - надійне зберігання даних
- 🐳 **Docker** - контейнеризація для легкого розгортання
- 🔍 **Пошук та фільтрація** - потужні можливості пошуку статей
- 📄 **Пагінація** - оптимізована робота з великими обсягами даних
- 🎯 **Playwright** - надійний веб-скрапинг з підтримкою JavaScript
- 📝 **Логування** - детальне логування всіх операцій

## 🛠️ Вимоги до системи

- **Docker** 
- **Docker Compose**
- **Git**
- **4GB RAM** (рекомендовано)
- **2GB** вільного місця на диску

## 🚀 Швидкий старт

1. **Клонуйте репозиторій:**
```bash
git clone <repository-url>
cd TT_scraper
```

2. **Запустіть за допомогою Docker:**
```bash
docker-compose up --build
```

3. **Відкрийте API в браузері:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- API: http://localhost:8000/api/v1/articles

## 📦 Встановлення

### Використання Docker (Рекомендовано)

1. **Клонуйте проект:**
```bash
git clone <repository-url>
cd TT_scraper
```

2. **Запустіть сервіси:**
```bash
# Запуск у фоновому режимі
docker-compose up -d --build

# Або з виводом логів
docker-compose up --build
```

3. **Перевірте статус:**
```bash
docker-compose ps
```

### Docker Compose

Файл `docker-compose.yml` містить конфігурацію для:

- **PostgreSQL** - база даних (порт 5432)
- **Scraper App** - основний додаток (порт 8000)
- **pgAdmin** - веб-інтерфейс для БД (порт 5050)

## 📚 API Документація

### Базові URL

- **Base URL**: `http://localhost:8000`
- **API Base**: `http://localhost:8000/api/v1`

### Endpoints

#### 📰 Статті

**GET /api/v1/articles**
```
Отримати список статей з пагінацією та фільтрацією

Query параметри:
- page: номер сторінки (за замовчуванням: 1)
- page_size: розмір сторінки (1-100, за замовчуванням: 20)
- search: пошук по заголовку та змісту
- author: фільтр по автору
- date_from: дата початку (YYYY-MM-DD)
- date_to: дата кінця (YYYY-MM-DD)
```

**GET /api/v1/articles/{id}**
```
Отримати статтю за ID
```

#### 🔧 Службові

**GET /**
```
Інформація про API
```

**GET /health**
```
Перевірка здоров'я сервісу
```

**GET /docs**
```
Swagger UI документація
```

**GET /redoc**
```
ReDoc документація
```

## 🎯 Використання

### Приклади HTTP запитів

1. **Отримати перші 10 статей:**
```bash
curl "http://localhost:8000/api/v1/articles?page=1&page_size=10"
```

2. **Пошук статей за ключовим словом:**
```bash
curl "http://localhost:8000/api/v1/articles?search=ukraine"
```

3. **Фільтрація за автором:**
```bash
curl "http://localhost:8000/api/v1/articles?author=John%20Smith"
```

4. **Фільтрація за датою:**
```bash
curl "http://localhost:8000/api/v1/articles?date_from=2024-01-01&date_to=2024-01-31"
```

5. **Комбінований запит:**
```bash
curl "http://localhost:8000/api/v1/articles?search=financial&page=1&page_size=5&date_from=2024-01-01"
```

### Приклад відповіді API

```json
{
  "articles": [
    {
      "id": 1,
      "url": "https://www.ft.com/content/...",
      "title": "Breaking: Financial Markets Update",
      "content": "Full article content...",
      "author": "Jane Doe",
      "published_at": "2024-01-20T10:00:00Z",
      "scraped_at": "2024-01-20T10:05:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### Python клієнт

```python
import requests

# Отримати статті
response = requests.get("http://localhost:8000/api/v1/articles")
data = response.json()

print(f"Знайдено {data['total']} статей")
for article in data['articles']:
    print(f"- {article['title']} by {article['author']}")
```

### JavaScript клієнт

```javascript
// Отримати статті
fetch('http://localhost:8000/api/v1/articles?page=1&page_size=5')
  .then(response => response.json())
  .then(data => {
    console.log(`Знайдено ${data.total} статей`);
    data.articles.forEach(article => {
      console.log(`- ${article.title} by ${article.author}`);
    });
  });
```

## 📁 Структура проекту

```
TT_scraper/
├── app/                     # Основний код додатку
│   ├── api/                 # FastAPI роутери та моделі
│   │   ├── app.py          # Головне FastAPI додаток
│   │   ├── models.py       # Pydantic моделі
│   │   └── routes.py       # API роутери
│   ├── db/                 # База даних
│   │   └── database.py     # Конфігурація SQLAlchemy
│   ├── models/             # ORM моделі
│   │   └── models.py       # SQLAlchemy моделі
│   ├── scheduler/          # Планувальник задач
│   │   └── scheduler.py    # APScheduler конфігурація
│   ├── scraper/            # Веб-скрапинг
│   │   └── scraper.py      # Playwright скрапер
│   ├── main.py             # Точка входу
│   └── api_server.py       # Тільки API сервер
├── tests/                  # Тести
├── logs/                   # Логи
├── data/                   # Тимчасові дані
├── docker-compose.yml      # Docker Compose конфігурація
├── Dockerfile              # Docker образ
├── requirements.txt        # Python залежності
└── README.md              # Ця документація
```

## 🧪 Розробка

### Локальна розробка

1. **Створіть віртуальне оточення:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# або
venv\Scripts\activate     # Windows
```

2. **Встановіть залежності:**
```bash
pip install -r requirements.txt
```

### Тестування

```bash
# Запуск всіх тестів
pytest

# Запуск з покриттям
pytest --cov=app

# Запуск конкретного тесту
pytest tests/test_scraper.py -v
```

### Моніторинг логів

```bash
# Дивитися логи в реальному часі
docker-compose logs -f scraper

# Логи бази даних
docker-compose logs postgres

# Всі логи
docker-compose logs
```

## 🔧 Troubleshooting

### Логи та відладка

- **Логи додатку**: `logs/scraper.log`
- **API логи**: В виводі Docker контейнера
- **БД логи**: `docker-compose logs postgres`

### Продуктивність

- Використовуйте індекси БД для швидкого пошуку
- Налаштуйте `page_size` відповідно до ваших потреб
- Моніторьте використання пам'яті при великих обсягах даних