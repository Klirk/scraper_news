"""
API маршруты для работы со статьями
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.models import Article
from app.api.models import (
    ArticleResponse, ArticleListResponse
)
# Роутеры для группировки endpoints
articles_router = APIRouter(prefix="/articles", tags=["Articles"])


# ARTICLES ENDPOINTS

@articles_router.get("/", response_model=ArticleListResponse)
async def get_articles(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
        search: Optional[str] = Query(None, description="Поиск по заголовку и содержимому"),
        author: Optional[str] = Query(None, description="Фильтр по автору"),
        date_from: Optional[datetime] = Query(None, description="Дата начала (published_at)"),
        date_to: Optional[datetime] = Query(None, description="Дата окончания (published_at)"),
        db: AsyncSession = Depends(get_session)
):
    """Получить список статей с пагинацией и фильтрацией"""

    # Базовый запрос
    query = select(Article)
    count_query = select(func.count(Article.id))

    # Применяем фильтры
    filters = []

    if search:
        search_filter = Article.title.ilike(f"%{search}%") | Article.content.ilike(f"%{search}%")
        filters.append(search_filter)

    if author:
        filters.append(Article.author.ilike(f"%{author}%"))

    if date_from:
        filters.append(Article.published_at >= date_from)

    if date_to:
        filters.append(Article.published_at <= date_to)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Считаем общее количество
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Применяем пагинацию и сортировку
    query = query.order_by(desc(Article.published_at))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Выполняем запрос
    result = await db.execute(query)
    articles = result.scalars().all()

    # Рассчитываем общее количество страниц
    total_pages = (total + page_size - 1) // page_size

    return ArticleListResponse(
        articles=[ArticleResponse.model_validate(article) for article in articles],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@articles_router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
        article_id: int,
        db: AsyncSession = Depends(get_session)
):
    """Получить статью по ID"""

    query = select(Article).where(Article.id == article_id)
    result = await db.execute(query)
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    return ArticleResponse.model_validate(article)



