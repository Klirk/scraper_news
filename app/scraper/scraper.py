"""
Основной модуль скрапинга Financial Times
"""
import asyncio
import datetime
import json
from pathlib import Path
from typing import  Optional

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
from loguru import logger


class FTScraper:
    """Скрапер для Financial Times с поддержкой авторизации и сохранения сессии"""

    def __init__(self):
        self.base_url = "https://www.ft.com"
        self.world_url = "https://www.ft.com/world"
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None