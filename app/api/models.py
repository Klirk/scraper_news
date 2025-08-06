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





class ErrorResponse(BaseModel):
    """Модель ошибки"""
    error: str
    detail: Optional[str] = None
