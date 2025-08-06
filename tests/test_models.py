"""
Тесты для моделей базы данных
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.models import Article


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_creation(test_db_session):
    """Тест создания модели Article"""
    # Создаем статью
    article = Article(
        url="https://www.ft.com/content/test-article",
        title="Test Article Title",
        content="This is test article content",
        author="Test Author",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    
    # Сохраняем в базу
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем что статья сохранилась
    assert article.id is not None
    assert article.url == "https://www.ft.com/content/test-article"
    assert article.title == "Test Article Title"
    assert article.content == "This is test article content"
    assert article.author == "Test Author"
    assert article.published_at is not None
    assert article.scraped_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_unique_constraint(test_db_session):
    """Тест уникальности URL статьи"""
    # Создаем первую статью
    article1 = Article(
        url="https://www.ft.com/content/duplicate-url",
        title="First Article",
        content="First article content",
        author="Author One",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    
    test_db_session.add(article1)
    await test_db_session.commit()
    
    # Пытаемся создать вторую статью с тем же URL
    article2 = Article(
        url="https://www.ft.com/content/duplicate-url",  # Тот же URL
        title="Second Article",
        content="Second article content",
        author="Author Two",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    
    test_db_session.add(article2)
    
    # Ожидаем ошибку уникальности
    with pytest.raises(IntegrityError):
        await test_db_session.commit()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_optional_author(test_db_session):
    """Тест создания статьи без автора"""
    # Создаем статью без автора
    article = Article(
        url="https://www.ft.com/content/no-author-article",
        title="Article Without Author",
        content="This article has no author",
        author=None,  # Автор не указан
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc)
    )
    
    # Сохраняем в базу
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем что статья сохранилась
    assert article.id is not None
    assert article.author is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_query(test_db_session):
    """Тест поиска статей в базе данных"""
    # Создаем несколько статей
    articles = [
        Article(
            url=f"https://www.ft.com/content/article-{i}",
            title=f"Article {i}",
            content=f"Content of article {i}",
            author=f"Author {i}",
            published_at=datetime.now(timezone.utc),
            scraped_at=datetime.now(timezone.utc)
        )
        for i in range(1, 4)
    ]
    
    # Сохраняем статьи
    for article in articles:
        test_db_session.add(article)
    await test_db_session.commit()
    
    # Ищем все статьи
    result = await test_db_session.execute(select(Article))
    all_articles = result.scalars().all()
    
    assert len(all_articles) == 3
    
    # Ищем статью по URL
    result = await test_db_session.execute(
        select(Article).where(Article.url == "https://www.ft.com/content/article-2")
    )
    found_article = result.scalar_one()
    
    assert found_article.title == "Article 2"
    assert found_article.author == "Author 2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_required_fields(test_db_session):
    """Тест обязательных полей модели Article"""
    # Пытаемся создать статью без обязательных полей
    with pytest.raises((ValueError, IntegrityError)):
        article = Article(
            # url отсутствует
            title="Test Title",
            content="Test Content",
            published_at=datetime.now(timezone.utc),
            scraped_at=datetime.now(timezone.utc)
        )
        test_db_session.add(article)
        await test_db_session.commit()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_article_datetime_fields(test_db_session):
    """Тест корректности полей даты и времени"""
    now = datetime.now(timezone.utc)
    
    article = Article(
        url="https://www.ft.com/content/datetime-test",
        title="DateTime Test Article",
        content="Testing datetime fields",
        author="DateTime Tester",
        published_at=now,
        scraped_at=now
    )
    
    test_db_session.add(article)
    await test_db_session.commit()
    
    # Проверяем что даты сохранились корректно
    assert article.published_at.tzinfo is not None
    assert article.scraped_at.tzinfo is not None
    assert article.published_at == now
    assert article.scraped_at == now


@pytest.mark.unit
def test_article_table_name():
    """Тест имени таблицы"""
    assert Article.__tablename__ == "articles"


@pytest.mark.unit
def test_article_string_lengths():
    """Тест максимальных длин строковых полей"""
    # Проверяем что поля имеют правильные ограничения длины
    url_column = Article.__table__.columns['url']
    title_column = Article.__table__.columns['title']
    author_column = Article.__table__.columns['author']
    
    assert url_column.type.length == 1024
    assert title_column.type.length == 512
    assert author_column.type.length == 255