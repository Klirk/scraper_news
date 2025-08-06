"""
Модели базы данных для хранения статей новостей.
Эти модели используются для хранения информации о новостных статьях
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Text, DateTime, UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped, mapped_column, DeclarativeBase
)


# SQLAlchemy ORM модели для работы с базой данных
class Base(DeclarativeBase):
    pass


# SQLAlchemy модель для хранения статей новостей
class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_article_url"),)  # Уникальный индекс по URL

    id: Mapped[int] = mapped_column(primary_key=True)

    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
