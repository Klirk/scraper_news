"""
Основной модуль скрапинга Financial Times
"""
import asyncio
import datetime
import json
import os
from pathlib import Path
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
    """Скрапер для Financial Times с поддержкой авторизации и сохранения сессии"""

    def __init__(self):
        self.base_url = "https://www.ft.com"
        self.login_url = "https://accounts.ft.com/login"
        self.world_url = "https://www.ft.com/world"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.session_file = Path("session_data.json")
        self.cookies_file = Path("cookies.json")
        self.is_authenticated = False

    async def init_browser(self) -> None:
        """Инициализация браузера"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=False)
            self.page = await self.browser.new_page()
            
    async def load_session(self) -> bool:
        """Загрузка сохраненной сессии"""
        try:
            if self.cookies_file.exists():
                logger.info("Загрузка сохраненной сессии...")
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                await self.page.context.add_cookies(cookies)
                
                # Проверяем, действительна ли сессия
                await self.page.goto(self.base_url)
                await asyncio.sleep(2)
                
                # Проверяем, авторизован ли пользователь
                if await self.check_authentication():
                    logger.success("Сессия успешно загружена!")
                    self.is_authenticated = True
                    return True
                else:
                    logger.warning("Сохраненная сессия недействительна")
                    return False
            else:
                logger.info("Файл сессии не найден")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка загрузки сессии: {e}")
            return False

    async def check_authentication(self) -> bool:
        """Проверка статуса авторизации"""
        try:
            # Ищем элементы, указывающие на авторизацию
            login_button = await self.page.query_selector("a[href*='login']")
            user_menu = await self.page.query_selector("[data-trackable='user-menu']")
            
            # Если есть меню пользователя и нет кнопки входа, значит авторизован
            if user_menu and not login_button:
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации: {e}")
            return False

    async def perform_login(self) -> bool:
        """Выполнение интерактивной авторизации"""
        try:
            logger.info("Начинаем процесс авторизации...")
            await self.page.goto(self.login_url)
            await asyncio.sleep(2)
            
            print("\n" + "="*60)
            print("АВТОРИЗАЦИЯ В FINANCIAL TIMES")
            print("="*60)
            print("Браузер открыт на странице входа.")
            print("Пожалуйста, выполните вход в свой аккаунт Financial Times.")
            print("После успешного входа нажмите Enter в этой консоли...")
            print("="*60)
            
            # Ждем, пока пользователь выполнит вход
            input("\nНажмите Enter после завершения входа: ")
            
            # Проверяем авторизацию
            if await self.check_authentication():
                logger.success("Авторизация успешна!")
                await self.save_session()
                self.is_authenticated = True
                return True
            else:
                logger.error("Авторизация не удалась. Проверьте правильность входа.")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            return False

    async def save_session(self) -> None:
        """Сохранение текущей сессии"""
        try:
            # Сохраняем cookies
            cookies = await self.page.context.cookies()
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            
            # Сохраняем дополнительную информацию о сессии
            session_data = {
                "saved_at": datetime.datetime.now().isoformat(),
                "base_url": self.base_url,
                "user_agent": await self.page.evaluate("navigator.userAgent")
            }
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            logger.success("Сессия сохранена!")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}")

    async def ensure_authentication(self) -> bool:
        """Обеспечение авторизации (загрузка или новая авторизация)"""
        if not self.page:
            await self.init_browser()
        
        # Пробуем загрузить существующую сессию
        if await self.load_session():
            return True
        
        # Если сессии нет или она недействительна, выполняем новую авторизацию
        logger.info("Требуется новая авторизация...")
        return await self.perform_login()

    async def close(self) -> None:
        """Закрытие браузера"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None