"""
Pydantic модели для FastAPI endpoints
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ArticleBase(BaseModel):
    """Базовая модель статьи"""
    url: str
    title: str
    content: str
    author: Optional[str] = None
    published_at: datetime


class ArticleResponse(ArticleBase):
    """Модель статьи для ответа API"""
    id: int
    scraped_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ArticleListResponse(BaseModel):
    """Модель для списка статей с пагинацией"""
    articles: List[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int





class StatusResponse(BaseModel):
    """Модель статуса системы"""
    database_status: str
    scheduler_status: str
    scheduler_jobs: List[dict]
    uptime: str


class StatsResponse(BaseModel):
    """Модель статистики"""
    total_articles: int
    articles_today: int
    articles_this_week: int
    articles_this_month: int
    latest_article_date: Optional[datetime] = None
    oldest_article_date: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """Модель ошибки"""
    error: str
    detail: Optional[str] = None