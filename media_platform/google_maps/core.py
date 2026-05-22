# -*- coding: utf-8 -*-

import asyncio
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from model.m_google_maps import GoogleMapsTask
from store import google_maps as google_maps_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import GoogleMapsClient
from .field import GoogleMapsTaskStatus
from .help import build_tasks, load_points_from_csv, resolve_points_file
from .login import GoogleMapsLogin


class GoogleMapsCrawler(AbstractCrawler):
    context_page: Page
    browser_context: BrowserContext
    google_maps_client: GoogleMapsClient
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = config.GOOGLE_MAPS_INDEX_URL
        self.cookie_urls = [self.index_url]
        self.user_agent = utils.get_user_agent()
        self.cdp_manager = None

    async def start(self):
        utils.logger.info("[GoogleMapsCrawler.start] Google Maps crawler starting ...")
        async with async_playwright() as playwright:
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[GoogleMapsCrawler.start] Launching browser in CDP mode")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    None,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[GoogleMapsCrawler.start] Launching browser in standard mode")
                self.browser_context = await self.launch_browser(
                    playwright.chromium,
                    None,
                    self.user_agent,
                    headless=config.HEADLESS,
                )

            self.context_page = await self.browser_context.new_page()
            self.google_maps_client = GoogleMapsClient(self.context_page)
            login_obj = GoogleMapsLogin(
                login_type=config.LOGIN_TYPE,
                browser_context=self.browser_context,
                context_page=self.context_page,
                cookie_str=config.COOKIES,
            )
            await login_obj.begin()

            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                await self.search()
            else:
                utils.logger.warning(
                    f"[GoogleMapsCrawler.start] Unsupported crawler type for google_maps: {config.CRAWLER_TYPE}. "
                    "Only search mode is supported."
                )

        utils.logger.info("[GoogleMapsCrawler.start] Google Maps crawler finished ...")

    async def search(self):
        points_file = resolve_points_file()
        points = load_points_from_csv(points_file)
        keywords = self._keywords()
        tasks = build_tasks(points, keywords)
        utils.logger.info(
            f"[GoogleMapsCrawler.search] Loaded points={len(points)} keywords={len(keywords)} tasks={len(tasks)} "
            f"source={points_file}"
        )
        await self._sync_task_catalog(points, tasks)

        limit = config.GOOGLE_MAPS_TASK_LIMIT
        runnable_tasks = tasks if limit == 0 else tasks[:limit]
        for task in runnable_tasks:
            if await self._should_skip_task(task):
                utils.logger.info(f"[GoogleMapsCrawler.search] Skip finished task={task.task_id}")
                continue
            source_keyword_var.set(task.keyword)
            await self._run_task(task)
            await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

    async def _run_task(self, task: GoogleMapsTask):
        await self._save_task_state(task, GoogleMapsTaskStatus.RUNNING.value)
        try:
            await self.google_maps_client.open_task_search(task)
            result_links = await self.google_maps_client.collect_result_links()
            utils.logger.info(
                f"[GoogleMapsCrawler._run_task] task={task.task_id} links={len(result_links)}"
            )
            if not result_links:
                await self._save_task_state(task, GoogleMapsTaskStatus.SUCCESS.value)
                return

            saved = 0
            for detail_url in result_links:
                shop = await self.google_maps_client.extract_shop_from_url(task, detail_url)
                if not shop.shop_id:
                    continue
                await google_maps_store.update_google_maps_shop(
                    shop,
                    task_id=task.task_id,
                    task_keyword=task.keyword,
                )
                saved += 1
            utils.logger.info(
                f"[GoogleMapsCrawler._run_task] task={task.task_id} saved_shops={saved}"
            )
            await self._save_task_state(task, GoogleMapsTaskStatus.SUCCESS.value)
        except Exception as exc:
            screenshot = await self._save_error_screenshot(task)
            utils.logger.error(
                f"[GoogleMapsCrawler._run_task] task={task.task_id} failed error={exc} screenshot={screenshot}"
            )
            await self._save_task_state(task, GoogleMapsTaskStatus.FAILED.value, str(exc))

    async def _save_task_state(self, task: GoogleMapsTask, status: str, last_error: str = ""):
        task.status = status
        task.last_error = last_error
        if status == GoogleMapsTaskStatus.FAILED.value:
            task.retry_count += 1
        task_item = {
            "task_id": task.task_id,
            "city": task.point.city,
            "address": task.point.address,
            "country": task.point.country,
            "crawl_lat": task.point.lat,
            "crawl_lng": task.point.lng,
            "keyword": task.keyword,
            "status": task.status,
            "retry_count": task.retry_count,
            "last_error": task.last_error,
        }
        await google_maps_store.update_google_maps_task(task_item)

    async def _sync_task_catalog(self, points, tasks: list[GoogleMapsTask]):
        if config.SAVE_DATA_OPTION not in {"db", "sqlite", "postgres"}:
            return
        point_items = [point.model_dump() for point in points]
        task_items = [
            {
                "task_id": task.task_id,
                "city": task.point.city,
                "address": task.point.address,
                "country": task.point.country,
                "crawl_lat": task.point.lat,
                "crawl_lng": task.point.lng,
                "keyword": task.keyword,
                "status": GoogleMapsTaskStatus.PENDING.value,
                "retry_count": 0,
                "last_error": "",
            }
            for task in tasks
        ]
        await google_maps_store.sync_google_maps_points_and_tasks(point_items, task_items)

    async def _should_skip_task(self, task: GoogleMapsTask) -> bool:
        if config.SAVE_DATA_OPTION not in {"db", "sqlite", "postgres"}:
            return False
        status = await google_maps_store.get_google_maps_task_status(task.task_id)
        return status == GoogleMapsTaskStatus.SUCCESS.value

    async def _save_error_screenshot(self, task: GoogleMapsTask) -> str:
        if not config.GOOGLE_MAPS_SCREENSHOT_ON_ERROR:
            return ""
        try:
            screenshot_dir = Path(config.SAVE_DATA_PATH or "data") / "google_maps" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"{task.task_id}.png"
            await self.context_page.screenshot(path=str(screenshot_path), full_page=True)
            return str(screenshot_path)
        except Exception:
            return ""

    @staticmethod
    def _keywords() -> list[str]:
        default_media_keywords = "编程副业,编程兼职"
        if config.KEYWORDS and config.KEYWORDS != default_media_keywords:
            return [keyword.strip() for keyword in config.KEYWORDS.split(",") if keyword.strip()]
        return list(config.GOOGLE_MAPS_KEYWORDS)

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            f"--lang={config.GOOGLE_MAPS_LOCALE}",
        ]
        launch_kwargs = {
            "headless": headless,
            "args": args,
            "proxy": playwright_proxy,
        }
        if config.GOOGLE_MAPS_USE_SYSTEM_CHROME and config.GOOGLE_MAPS_CHROME_EXECUTABLE_PATH:
            launch_kwargs["executable_path"] = config.GOOGLE_MAPS_CHROME_EXECUTABLE_PATH
        browser = await chromium.launch(**launch_kwargs)
        return await browser.new_context(
            user_agent=user_agent,
            locale=config.GOOGLE_MAPS_LOCALE,
            timezone_id=config.GOOGLE_MAPS_TIMEZONE,
            viewport={"width": 1440, "height": 1000},
        )

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        self.cdp_manager = CDPBrowserManager()
        return await self.cdp_manager.launch_and_connect(
            playwright=playwright,
            playwright_proxy=playwright_proxy,
            user_agent=user_agent,
            headless=headless,
        )
