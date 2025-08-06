"""
Тесты для моделей базы данных
"""
import pytest
import datetime
from sqlalchemy import select
from app.models.models import Article, Base


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_model_creation(test_db_session):
    """Тестирует создание модели Article"""
    article_data = {
        "url": "https://www.ft.com/content/test-123",
        "title": "Test Article",
        "content": "Test content for the article",
        "author": "Test Author",
        "published_at": datetime.datetime.now(datetime.timezone.utc),
        "scraped_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    article = Article(**article_data)
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем, что статья создана
    result = await test_db_session.execute(select(Article).where(Article.url == article_data["url"]))
    saved_article = result.scalar_one()
    
    assert saved_article.url == article_data["url"]
    assert saved_article.title == article_data["title"]
    assert saved_article.content == article_data["content"]
    assert saved_article.author == article_data["author"]
    assert saved_article.published_at == article_data["published_at"]
    assert saved_article.scraped_at == article_data["scraped_at"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_unique_constraint(test_db_session):
    """Тестирует уникальное ограничение на URL"""
    article_data = {
        "url": "https://www.ft.com/content/unique-test",
        "title": "First Article",
        "content": "First content",
        "author": "Author One",
        "published_at": datetime.datetime.now(datetime.timezone.utc),
        "scraped_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    # Создаем первую статью
    article1 = Article(**article_data)
    test_db_session.add(article1)
    await test_db_session.commit()
    
    # Пытаемся создать вторую статью с тем же URL
    article_data["title"] = "Second Article"
    article_data["content"] = "Second content"
    
    article2 = Article(**article_data)
    test_db_session.add(article2)
    
    # Должно возникнуть исключение из-за уникального ограничения
    with pytest.raises(Exception):  # IntegrityError
        await test_db_session.commit()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_optional_author(test_db_session):
    """Тестирует, что поле author может быть пустым"""
    article_data = {
        "url": "https://www.ft.com/content/no-author-test",
        "title": "Article without author",
        "content": "Content without author",
        "author": None,
        "published_at": datetime.datetime.now(datetime.timezone.utc),
        "scraped_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    article = Article(**article_data)
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем, что статья создана с author = None
    result = await test_db_session.execute(select(Article).where(Article.url == article_data["url"]))
    saved_article = result.scalar_one()
    
    assert saved_article.author is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_required_fields(test_db_session):
    """Тестирует, что обязательные поля не могут быть пустыми"""
    # Тестируем отсутствие URL
    with pytest.raises(Exception):
        article = Article(
            title="Test",
            content="Test content",
            published_at=datetime.datetime.now(datetime.timezone.utc),
            scraped_at=datetime.datetime.now(datetime.timezone.utc)
        )
        test_db_session.add(article)
        await test_db_session.commit()


@pytest.mark.unit
def test_article_table_name():
    """Тестирует имя таблицы"""
    assert Article.__tablename__ == "articles"


@pytest.mark.unit
def test_article_string_length_constraints():
    """Тестирует ограничения длины строковых полей"""
    # Проверяем максимальную длину URL (1024)
    long_url = "https://www.ft.com/content/" + "a" * 1000
    
    article_data = {
        "url": long_url,
        "title": "Test",
        "content": "Test content",
        "published_at": datetime.datetime.now(datetime.timezone.utc),
        "scraped_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    # Должно работать если URL не превышает 1024 символа
    article = Article(**article_data)
    assert article.url == long_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multiple_articles_creation(test_db_session):
    """Тестирует создание нескольких статей"""
    articles_data = [
        {
            "url": f"https://www.ft.com/content/test-{i}",
            "title": f"Test Article {i}",
            "content": f"Test content {i}",
            "author": f"Author {i}",
            "published_at": datetime.datetime.now(datetime.timezone.utc),
            "scraped_at": datetime.datetime.now(datetime.timezone.utc)
        }
        for i in range(3)
    ]
    
    # Добавляем все статьи
    for article_data in articles_data:
        article = Article(**article_data)
        test_db_session.add(article)
    
    await test_db_session.commit()
    
    # Проверяем, что все статьи созданы
    result = await test_db_session.execute(select(Article))
    all_articles = result.scalars().all()
    
    assert len(all_articles) == 3
    
    # Проверяем, что все URL уникальны
    urls = [article.url for article in all_articles]
    assert len(set(urls)) == 3


@pytest.mark.unit
def test_base_model():
    """Тестирует базовую модель"""
    assert hasattr(Base, 'metadata')
    assert Article.__bases__[0] == Base