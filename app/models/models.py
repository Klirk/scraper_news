from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Text, DateTime, Integer,
    Table, Column, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship, DeclarativeBase
)


# Моделі для SQLAlchemy ORM
class Base(DeclarativeBase):
    pass

# Модель для статей
class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("url", name="uq_article_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # додаткові поля
    subtitle: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reading_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # зв’язок з тегами
    tags: Mapped[List["Tag"]] = relationship(
        back_populates="articles",
        secondary=article_tag_association,
        lazy="selectin"
    )

    # зв’язок із пов'язаними статтями через окрему таблицю
    related_articles: Mapped[List["RelatedArticle"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class RelatedArticle(Base):
    __tablename__ = "related_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False)
    related_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    article: Mapped["Article"] = relationship(back_populates="related_articles")

