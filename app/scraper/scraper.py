"""
Основной модуль скрапинга Financial Times
"""
import asyncio
import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser, ViewportSize
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.db.database import get_session
from app.models.models import Article
from sqlalchemy import select, func


class FTScraper:
    """Скрапер для Financial Times с поддержкой авторизации и сохранения сессии"""

    def __init__(self):
        self.base_url = "https://www.ft.com"
        self.world_url = "https://www.ft.com/world"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def init_browser(self, max_retries: int = 3) -> None:
        """Инициализация браузера с повторными попытками"""
        for attempt in range(max_retries):
            try:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox', 
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions',
                        '--no-first-run'
                    ]
                )
                context = await self.browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport=ViewportSize(width=1920, height=1080)
                )
                
                # Устанавливаем таймауты
                context.set_default_timeout(30000)  # 30 секунд
                context.set_default_navigation_timeout(30000)
                
                self.page = await context.new_page()
                logger.info("🌐 Браузер успешно инициализирован")
                return
                
            except Exception as e:
                logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} инициализации браузера неудачна: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                else:
                    logger.error(f"❌ Не удалось инициализировать браузер после {max_retries} попыток")
                    raise

    async def close_browser(self) -> None:
        """Закрытие браузера"""
        try:
            if self.browser:
                await self.browser.close()
                logger.info("🔴 Браузер закрыт")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия браузера: {e}")

    @staticmethod
    async def is_first_run() -> bool:
        """Проверка, является ли запуск первым (нет статей в базе)"""
        try:
            async for session in get_session():
                result = await session.execute(select(func.count(Article.id)))
                count = result.scalar()
                is_first = count == 0
                logger.info(f"📊 Статей в базе: {count}, первый запуск: {is_first}")
                return is_first
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка проверки первого запуска: {e}")
            return True  # По умолчанию считаем первым запуском

    @staticmethod
    def _is_article_recent(published_at: datetime.datetime, hours_limit: int = 1) -> bool:
        """Проверка, является ли статья недавней (в пределах указанного количества часов)"""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_limit = now - datetime.timedelta(hours=hours_limit)
        return published_at >= time_limit

    @staticmethod
    def _is_article_within_days(published_at: datetime.datetime, days_limit: int = 30) -> bool:
        """Проверка, является ли статья в пределах указанного количества дней"""
        now = datetime.datetime.now(datetime.timezone.utc)
        time_limit = now - datetime.timedelta(days=days_limit)
        return published_at >= time_limit

    @staticmethod
    def _parse_publish_date(date_str: str) -> datetime.datetime:
        """Парсинг даты публикации из атрибута title"""
        try:
            date_obj = datetime.datetime.strptime(date_str, "%B %d %Y %I:%M %p")
            return date_obj.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            logger.warning(f"⚠️ Не удалось распарсить дату: {date_str}")
            return datetime.datetime.now(datetime.timezone.utc)

    def _extract_article_data(self, article_element, time_filter_func=None) -> Optional[Dict[str, Any]]:
        """Извлечение данных статьи из HTML элемента с опциональной фильтрацией по времени"""
        try:
            # Проверяем, не является ли статья премиум
            premium_label = article_element.find('span', class_='o-labels--premium')
            if premium_label:
                logger.debug("⏭️ Пропускаем премиум статью")
                return None

            # Извлекаем автора (категорию)
            author_element = article_element.find('a', class_='o-teaser__tag')
            author = author_element.get_text(strip=True) if author_element else "Unknown"

            # Извлекаем заголовок и URL
            title_element = article_element.find('a', class_='js-teaser-heading-link')
            if not title_element:
                logger.warning("⚠️ Не найден заголовок статьи")
                return None
            
            title = title_element.get_text(strip=True)
            relative_url = title_element.get('href')
            full_url = urljoin(self.base_url, relative_url)

            # Извлекаем краткое описание
            standfirst_element = article_element.find('a', class_='js-teaser-standfirst-link')
            content = standfirst_element.get_text(strip=True) if standfirst_element else ""

            # Извлекаем дату публикации
            time_element = article_element.find('time')
            if time_element and time_element.get('title'):
                published_at = self._parse_publish_date(time_element.get('title'))
            else:
                published_at = datetime.datetime.now(datetime.timezone.utc)

            # Применяем фильтр по времени если он задан
            if time_filter_func and not time_filter_func(published_at):
                logger.debug(f"⏭️ Пропускаем статью по времени: {title[:50]}...")
                return None

            return {
                'url': full_url,
                'title': title,
                'content': content,
                'author': author,
                'published_at': published_at,
                'scraped_at': datetime.datetime.now(datetime.timezone.utc)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка извлечения данных статьи: {e}")
            return None

    async def scrape_single_page(self, page_num: int = 1, time_filter_func=None, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Скрапинг одной страницы статей с повторными попытками"""
        for attempt in range(max_retries):
            try:
                # Формируем URL страницы
                if page_num == 1:
                    url = self.world_url
                else:
                    url = f"{self.world_url}?page={page_num}"
                
                logger.info(f"📄 Скрапинг страницы {page_num} (попытка {attempt + 1}/{max_retries}): {url}")
                
                # Переходим на страницу с обработкой таймаутов
                try:
                    await self.page.goto(url, wait_until='networkidle', timeout=30000)
                except Exception as nav_error:
                    logger.warning(f"⚠️ Ошибка навигации на страницу {page_num}: {nav_error}")
                    # Пробуем без ожидания networkidle
                    await self.page.goto(url, wait_until='load', timeout=30000)
                
                # Ждем загрузки контента
                await asyncio.sleep(2)
                
                # Ждем появления списка статей
                try:
                    await self.page.wait_for_selector('ul.o-teaser-collection__list', timeout=10000)
                except TimeoutError:
                    logger.warning(f"⚠️ Список статей не найден на странице {page_num}")

                # Получаем HTML контент
                content = await self.page.content()
                soup = BeautifulSoup(content, 'html.parser')

                # Находим список статей
                articles_list = soup.find('ul', class_='o-teaser-collection__list')
                if not articles_list:
                    logger.warning(f"⚠️ Не найден список статей на странице {page_num}")
                    return []

                # Извлекаем все элементы статей
                article_items = articles_list.find_all('li', class_='o-teaser-collection__item')
                logger.info(f"🔍 Найдено {len(article_items)} элементов статей на странице {page_num}")

                articles_data = []
                for item in article_items:
                    try:
                        article_data = self._extract_article_data(item, time_filter_func)
                        if article_data:
                            articles_data.append(article_data)
                    except Exception as extract_error:
                        logger.warning(f"⚠️ Ошибка извлечения данных статьи: {extract_error}")
                        continue

                logger.info(f"✅ Успешно извлечено {len(articles_data)} статей со страницы {page_num}")
                return articles_data

            except Exception as e:
                logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} скрапинга страницы {page_num} неудачна: {e}")
                if attempt < max_retries - 1:
                    # Экспоненциальная задержка между попытками
                    delay = min(2 ** attempt, 10)  # Максимум 10 секунд
                    logger.info(f"⏳ Ожидание {delay} секунд перед повторной попыткой...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Не удалось скрапить страницу {page_num} после {max_retries} попыток")
                    
        return []  # Возвращаем пустой список если все попытки неудачны

    async def scrape_articles_with_pagination(self, max_pages: int = 10, time_filter_func=None) -> List[Dict[str, Any]]:
        """Скрапинг статей с пагинацией"""
        try:
            logger.info(f"📚 Начинаем скрапинг с пагинацией (макс. {max_pages} страниц)...")
            
            all_articles = []
            no_articles_count = 0
            page_num = 0
            
            for page_num in range(1, max_pages + 1):
                page_articles = await self.scrape_single_page(page_num, time_filter_func)
                
                if not page_articles:
                    no_articles_count += 1
                    logger.warning(f"⚠️ Страница {page_num} не содержит подходящих статей")
                    
                    # Если 3 страницы подряд без статей - прекращаем
                    if no_articles_count >= 3:
                        logger.info("🛑 Найдено 3 страницы подряд без статей, прекращаем скрапинг")
                        break
                else:
                    no_articles_count = 0  # Сбрасываем счетчик
                    all_articles.extend(page_articles)
                    
                    # При использовании временного фильтра проверяем последнюю статью
                    if time_filter_func and page_articles:
                        last_article_date = page_articles[-1]['published_at']
                        # Если последняя статья на странице слишком старая, прекращаем
                        if not time_filter_func(last_article_date):
                            logger.info(f"🕐 Достигнут временной лимит на странице {page_num}, прекращаем скрапинг")
                            break
                
                # Небольшая пауза между страницами
                await asyncio.sleep(1)
            
            logger.info(f"🎉 Завершен скрапинг с пагинацией: собрано {len(all_articles)} статей с {page_num} страниц")
            return all_articles

        except Exception as e:
            logger.error(f"❌ Ошибка скрапинга с пагинацией: {e}")
            return []

    async def scrape_articles_list(self, time_filter_func=None) -> List[Dict[str, Any]]:
        """Скрапинг списка статей с главной страницы мира (без пагинации)"""
        return await self.scrape_single_page(1, time_filter_func)

    @staticmethod
    async def save_articles_to_db(articles_data: List[Dict[str, Any]], max_retries: int = 3) -> int:
        """Сохранение статей в базу данных с обработкой ошибок"""
        saved_count = 0
        failed_count = 0
        
        if not articles_data:
            logger.info("📝 Нет статей для сохранения")
            return 0
        
        for attempt in range(max_retries):
            try:
                async for session in get_session():
                    batch_saved = 0
                    
                    for i, article_data in enumerate(articles_data):
                        try:
                            # Валидация данных перед сохранением
                            if not all(key in article_data for key in ['url', 'title', 'content']):
                                logger.warning(f"⚠️ Пропущена статья с неполными данными: {article_data.get('title', 'Unknown')}")
                                continue
                            
                            # Создаем объект статьи
                            article = Article(**article_data)
                            
                            # Добавляем в сессию
                            session.add(article)
                            await session.commit()
                            batch_saved += 1
                            saved_count += 1
                            logger.debug(f"💾 Сохранена статья: {article.title[:50]}...")
                            
                        except IntegrityError:
                            # Статья уже существует (дублирование по URL)
                            await session.rollback()
                            logger.debug(f"⏭️ Статья уже существует: {article_data.get('title', 'Unknown')[:50]}...")
                            continue
                            
                        except Exception as e:
                            await session.rollback()
                            failed_count += 1
                            logger.warning(f"⚠️ Ошибка сохранения статьи {i+1}: {e}")
                            
                            # Если много ошибок подряд, прерываем
                            if failed_count > 5:
                                logger.error("❌ Слишком много ошибок сохранения, прерываем операцию")
                                break
                            continue
                    
                    logger.info(f"📦 Обработан batch: сохранено {batch_saved} статей")
                    break  # Успешно завершили, выходим из цикла попыток
                    
            except Exception as e:
                logger.warning(f"⚠️ Попытка {attempt + 1}/{max_retries} сохранения в БД неудачна: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                else:
                    logger.error(f"❌ Не удалось сохранить данные в БД после {max_retries} попыток")
        
        logger.info(f"✅ Итого сохранено {saved_count} новых статей в базу данных")
        if failed_count > 0:
            logger.warning(f"⚠️ Не удалось сохранить {failed_count} статей из-за ошибок")
            
        return saved_count

    async def run_scraping(self) -> None:
        """Основной метод запуска скрапинга с автоматическим определением режима"""
        try:
            logger.info("🚀 Запуск скрапинга Financial Times...")
            
            # Инициализируем браузер
            await self.init_browser()
            
            # Определяем режим работы
            is_first = await self.is_first_run()
            
            if is_first:
                # Первый запуск - собираем статьи за последние 30 дней
                logger.info("🆕 Первый запуск - собираем статьи за последние 30 дней...")
                time_filter = lambda date: self._is_article_within_days(date, 30)
                articles_data = await self.scrape_articles_with_pagination(
                    max_pages=100,
                    time_filter_func=time_filter
                )
            else:
                # Обычный запуск - собираем статьи за последний час
                logger.info("⏰ Обычный запуск - собираем статьи за последний час...")
                time_filter = lambda date: self._is_article_recent(date, 1)
                articles_data = await self.scrape_articles_with_pagination(
                    max_pages=5,  # Максимум 5 страниц для сбора за час
                    time_filter_func=time_filter
                )
            
            if articles_data:
                # Сохраняем в базу данных
                saved_count = await self.save_articles_to_db(articles_data)
                logger.info(f"🎉 Скрапинг завершен! Обработано: {len(articles_data)}, сохранено: {saved_count}")
            else:
                logger.warning("⚠️ Не удалось получить данные статей")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка скрапинга: {e}")
        finally:
            # Закрываем браузер
            await self.close_browser()

    async def run_initial_scraping(self) -> None:
        """Принудительный запуск сбора статей за 30 дней (для первого запуска)"""
        try:
            logger.info("🔄 Принудительный сбор статей за 30 дней...")
            
            await self.init_browser()
            
            time_filter = lambda date: self._is_article_within_days(date, 30)
            articles_data = await self.scrape_articles_with_pagination(
                max_pages=50,
                time_filter_func=time_filter
            )
            
            if articles_data:
                saved_count = await self.save_articles_to_db(articles_data)
                logger.info(f"🎉 Принудительный сбор завершен! Обработано: {len(articles_data)}, сохранено: {saved_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка принудительного сбора: {e}")
        finally:
            await self.close_browser()

    async def run_hourly_scraping(self) -> None:
        """Запуск сбора статей за последний час"""
        try:
            logger.info("⏱️ Сбор новых статей за последний час...")
            
            await self.init_browser()
            
            time_filter = lambda date: self._is_article_recent(date, 1)
            articles_data = await self.scrape_articles_with_pagination(
                max_pages=5,
                time_filter_func=time_filter
            )
            
            if articles_data:
                saved_count = await self.save_articles_to_db(articles_data)
                logger.info(f"🎉 Почасовой сбор завершен! Обработано: {len(articles_data)}, сохранено: {saved_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка почасового сбора: {e}")
        finally:
            await self.close_browser()