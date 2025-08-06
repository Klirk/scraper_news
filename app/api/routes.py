"""
API маршруты для работы со статьями и скрапером
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.models import Article
from app.api.models import (
    ArticleResponse, ArticleListResponse, StatusResponse, StatsResponse
)
from app.scraper.scraper import FTScraper
from app.scheduler.scheduler import ScrapingScheduler

# Роутеры для группировки endpoints
articles_router = APIRouter(prefix="/articles", tags=["Articles"])
system_router = APIRouter(prefix="/system", tags=["System"])

# Глобальные переменные для скрапера и планировщика
_scraper_instance: Optional[FTScraper] = None
_scheduler_instance: Optional[ScrapingScheduler] = None


def get_scraper() -> FTScraper:
    """Получить экземпляр скрапера"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = FTScraper()
    return _scraper_instance


def get_scheduler() -> ScrapingScheduler:
    """Получить экземпляр планировщика"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ScrapingScheduler()
    return _scheduler_instance


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

# SYSTEM ENDPOINTS

@system_router.get("/status", response_model=StatusResponse)
async def get_system_status(
    db: AsyncSession = Depends(get_session),
    scheduler: ScrapingScheduler = Depends(get_scheduler)
):
    """Получить статус системы"""
    
    # Проверяем статус базы данных
    try:
        await db.execute(select(func.count(Article.id)))
        db_status = "connected"
    except Exception:
        db_status = "error"
    
    # Получаем информацию о планировщике
    scheduler_status = "running" if scheduler.scheduler.running else "stopped"
    
    # Получаем список задач планировщика
    jobs = []
    for job in scheduler.scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return StatusResponse(
        database_status=db_status,
        scheduler_status=scheduler_status,
        scheduler_jobs=jobs,
        uptime="unknown"  # Можно добавить отслеживание времени работы
    )


@system_router.get("/stats", response_model=StatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_session)):
    """Получить статистику системы"""
    
    # Общее количество статей
    total_result = await db.execute(select(func.count(Article.id)))
    total_articles = total_result.scalar()
    
    # Статьи за сегодня
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    today_result = await db.execute(
        select(func.count(Article.id)).where(
            and_(Article.published_at >= today_start, Article.published_at <= today_end)
        )
    )
    articles_today = today_result.scalar()
    
    # Статьи за неделю
    week_ago = datetime.now() - timedelta(days=7)
    week_result = await db.execute(
        select(func.count(Article.id)).where(Article.published_at >= week_ago)
    )
    articles_this_week = week_result.scalar()
    
    # Статьи за месяц
    month_ago = datetime.now() - timedelta(days=30)
    month_result = await db.execute(
        select(func.count(Article.id)).where(Article.published_at >= month_ago)
    )
    articles_this_month = month_result.scalar()
    
    # Самая новая и старая статья
    latest_result = await db.execute(
        select(func.max(Article.published_at))
    )
    latest_date = latest_result.scalar()
    
    oldest_result = await db.execute(
        select(func.min(Article.published_at))
    )
    oldest_date = oldest_result.scalar()
    
    return StatsResponse(
        total_articles=total_articles,
        articles_today=articles_today,
        articles_this_week=articles_this_week,
        articles_this_month=articles_this_month,
        latest_article_date=latest_date,
        oldest_article_date=oldest_date
    )