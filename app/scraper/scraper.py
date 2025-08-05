"""
Основной модуль скрапинга Financial Times
"""
import asyncio
import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.models import Article, Tag, RelatedArticle
from app.db.database import get_session


class FTScraper:
    """Скрапер для Financial Times"""

    def __init__(self):
        self.base_url = "https://www.ft.com"
        self.world_url = "https://www.ft.com/world"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """Async context manager entry"""
        playwright = await async_playwright().start()


        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--no-first-run',
                '--disable-default-apps'
            ]
        )

        # Создаем страницу с настройками
        self.page = await self.browser.new_page()
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()


    async def get_article_links(self, days_back: int = 1) -> List[Dict[str, Any]]:
        """
        Получает ссылки на статьи из раздела World

        Args:
            days_back: Количество дней назад для поиска статей

        Returns:
            List[Dict]: Список словарей с информацией о статьях
        """
        logger.info(f"🔍 Getting article links for last {days_back} days")

        try:
            await self.page.goto(self.world_url, wait_until='networkidle')
            await asyncio.sleep(2)

            # Получаем HTML контент
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            article_links = []

            # Ищем статьи по различным селекторам
            selectors = [
                'a[data-trackable="heading-link"]',
                'a[href*="/content/"]',
                '.o-teaser__heading a',
                '.js-teaser-heading-link'
            ]

            for selector in selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and self._is_valid_article_url(href):
                        full_url = urljoin(self.base_url, href)
                        title = link.get('title') or link.get_text(strip=True)

                        if title and len(title) > 10:  # Фильтр коротких заголовков
                            article_links.append({
                                'url': full_url,
                                'title': title,
                                'found_at': datetime.datetime.now(datetime.UTC)
                            })

            # Удаляем дубликаты
            unique_links = {}
            for item in article_links:
                unique_links[item['url']] = item

            logger.info(f"📄 Found {len(unique_links)} unique articles")
            return list(unique_links.values())

        except Exception as e:
            logger.error(f"❌ Error getting article links: {str(e)}")
            return []

    @staticmethod
    def _is_valid_article_url(url: str) -> bool:
        """Проверяет, является ли URL валидной ссылкой на статью"""
        if not url:
            return False

        # Исключаем нежелательные URL
        exclude_patterns = [
            '/video/', '/podcast/', '/live-news/',
            '/markets/', '/opinion/', '/lex/',
            'mailto:', 'javascript:', '#', '?'
        ]

        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False

        # Проверяем, что это статья
        return '/content/' in url or url.startswith('/world/')

    async def scrape_article(self, article_url: str) -> Optional[Dict[str, Any]]:
        """
        Скрапит отдельную статью

        Args:
            article_url: URL статьи

        Returns:
            Dict или None: Данные статьи или None если ошибка
        """
        try:
            logger.debug(f"📖 Scraping article: {article_url}")

            await self.page.goto(article_url, wait_until='networkidle')
            await asyncio.sleep(1)

            # Проверяем на paywall
            if await self._is_paywall():
                logger.warning(f"💰 Paywall detected, skipping: {article_url}")
                return None

            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Извлекаем данные
            article_data = {
                'url': article_url,
                'title': self._extract_title(soup),
                'content': self._extract_content(soup),
                'author': self._extract_author(soup),
                'published_at': self._extract_published_date(soup),
                'subtitle': self._extract_subtitle(soup),
                'image_url': self._extract_image_url(soup),
                'tags': self._extract_tags(soup),
                'related_articles': self._extract_related_articles(soup),
                'scraped_at': datetime.datetime.now(datetime.UTC)
            }

            # Подсчитываем слова и время чтения
            if article_data['content']:
                word_count = len(article_data['content'].split())
                article_data['word_count'] = word_count
                article_data['reading_time'] = f"{max(1, word_count // 200)} min read"

            # Проверяем обязательные поля
            if not all([article_data['title'], article_data['content']]):
                logger.warning(f"⚠️ Missing required fields for: {article_url}")
                return None

            logger.success(f"✅ Successfully scraped: {article_data['title'][:50]}...")
            return article_data

        except Exception as e:
            logger.error(f"❌ Error scraping article {article_url}: {str(e)}")
            return None

    async def _is_paywall(self) -> bool:
        """Проверяет наличие paywall на странице"""
        paywall_selectors = [
            '.barrier-page',
            '.subscription-banner',
            '[data-trackable="subscribe-banner"]',
            '.o-banner--subscription'
        ]

        for selector in paywall_selectors:
            if await self.page.query_selector(selector):
                return True

        # Проверяем по тексту
        page_text = await self.page.text_content('body')
        paywall_texts = [
            'Subscribe to read',
            'Premium subscribers only',
            'Try full digital access'
        ]

        return any(text in page_text for text in paywall_texts)

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        selectors = [
            'h1.n-content-header--headline',
            'h1[data-trackable="headline"]',
            '.article-headline h1',
            'h1.o-typography-headline--large'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        # Fallback к title страницы
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            return title.replace(' | Financial Times', '')

        return ""

    @staticmethod
    def _extract_content(soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи"""
        selectors = [
            '.n-content-body',
            '[data-trackable="story-body"]',
            '.article-body',
            '.o-editorial-typography-body'
        ]

        for selector in selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Удаляем ненужные элементы
                for tag in content_div.find_all(['script', 'style', 'aside', 'nav']):
                    tag.decompose()

                paragraphs = content_div.find_all(['p', 'div'], recursive=True)
                content_parts = []

                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:  # Фильтр коротких параграфов
                        content_parts.append(text)

                return '\n\n'.join(content_parts)

        return ""

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> Optional[str]:
        """Извлекает автора статьи"""
        selectors = [
            '[data-trackable="author"]',
            '.n-content-header--byline a',
            '.article-author',
            '.byline a'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return None

    @staticmethod
    def _extract_published_date(soup: BeautifulSoup) -> datetime.datetime:
        """Извлекает дату публикации"""
        selectors = [
            'time[datetime]',
            '[data-trackable="timestamp"]',
            '.article-timestamp'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                datetime_str = element.get('datetime')
                if datetime_str:
                    try:
                        return datetime.datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    except ValueError:
                        pass

                # Пробуем извлечь из текста
                text = element.get_text(strip=True)
                if text:
                    # Здесь можно добавить парсинг различных форматов дат
                    pass

        # Fallback - текущее время
        return datetime.datetime.now(datetime.UTC)

    @staticmethod
    def _extract_subtitle(soup: BeautifulSoup) -> Optional[str]:
        """Извлекает подзаголовок"""
        selectors = [
            '.n-content-header--standfirst',
            '[data-trackable="standfirst"]',
            '.article-subtitle',
            '.o-editorial-typography-standfirst'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return None

    def _extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлекает URL главного изображения"""
        selectors = [
            '.n-image img',
            '.article-image img',
            '.o-editorial-layout-wrapper img'
        ]

        for selector in selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get('src') or img.get('data-src')
                if src:
                    return urljoin(self.base_url, src)

        return None

    @staticmethod
    def _extract_tags(soup: BeautifulSoup) -> List[str]:
        """Извлекает теги статьи"""
        tags = []

        # Ищем теги в различных местах
        tag_selectors = [
            '[data-trackable="topic"] a',
            '.article-tags a',
            '.topics a'
        ]

        for selector in tag_selectors:
            elements = soup.select(selector)
            for element in elements:
                tag = element.get_text(strip=True)
                if tag and tag not in tags:
                    tags.append(tag)

        return tags[:10]  # Ограничиваем количество тегов

    def _extract_related_articles(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает ссылки на связанные статьи"""
        related_urls = []

        selectors = [
            '.related-articles a[href*="/content/"]',
            '.recommended-articles a[href*="/content/"]',
            '.more-on a[href*="/content/"]'
        ]

        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and self._is_valid_article_url(href):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in related_urls:
                        related_urls.append(full_url)

        return related_urls[:5]  # Ограничиваем количество


class ArticleProcessor:
    """Класс для обработки и сохранения статей в базу данных"""

    async def save_article(self, article_data: Dict[str, Any]) -> bool:
        """
        Сохраняет статью в базу данных

        Args:
            article_data: Данные статьи

        Returns:
            bool: True если успешно сохранено
        """
        try:
            async with get_session() as session:
                # Проверяем, существует ли статья
                existing = await session.execute(
                    select(Article).where(Article.url == article_data['url'])
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"📄 Article already exists: {article_data['url']}")
                    return False

                # Создаем статью
                article = Article(
                    url=article_data['url'],
                    title=article_data['title'],
                    content=article_data['content'],
                    author=article_data.get('author'),
                    published_at=article_data['published_at'],
                    scraped_at=article_data['scraped_at'],
                    subtitle=article_data.get('subtitle'),
                    image_url=article_data.get('image_url'),
                    word_count=article_data.get('word_count'),
                    reading_time=article_data.get('reading_time')
                )

                # Обрабатываем теги
                if article_data.get('tags'):
                    for tag_name in article_data['tags']:
                        tag = await self._get_or_create_tag(session, tag_name)
                        article.tags.append(tag)

                session.add(article)
                await session.flush()  # Получаем ID статьи

                # Добавляем связанные статьи
                if article_data.get('related_articles'):
                    for related_url in article_data['related_articles']:
                        related_article = RelatedArticle(
                            article_id=article.id,
                            related_url=related_url
                        )
                        session.add(related_article)

                await session.commit()
                logger.success(f"💾 Saved article: {article_data['title'][:50]}...")
                return True

        except IntegrityError:
            logger.warning(f"⚠️ Duplicate article: {article_data['url']}")
            return False
        except Exception as e:
            logger.error(f"❌ Error saving article: {str(e)}")
            return False

    @staticmethod
    async def _get_or_create_tag(session: AsyncSession, tag_name: str) -> Tag:
        """Получает существующий тег или создает новый"""
        # Ищем существующий тег
        result = await session.execute(
            select(Tag).where(Tag.name == tag_name)
        )
        tag = result.scalar_one_or_none()

        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
            await session.flush()

        return tag