# -*- coding: utf-8 -*-

from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractLogin
from tools import utils


class GoogleMapsLogin(AbstractLogin):
    def __init__(
        self,
        login_type: str,
        browser_context: BrowserContext,
        context_page: Page,
        cookie_str: str = "",
    ) -> None:
        self.login_type = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.cookie_str = cookie_str

    async def begin(self):
        if self.login_type == "cookie" and self.cookie_str:
            await self.login_by_cookies()
            return
        utils.logger.info(
            "[GoogleMapsLogin.begin] Google Maps uses the current browser profile/login state. "
            "If login is required, sign in manually in the CDP browser."
        )
        await self.context_page.goto(f"{config.GOOGLE_MAPS_INDEX_URL}?hl={config.GOOGLE_MAPS_LOCALE}")

    async def login_by_qrcode(self):
        return await self.begin()

    async def login_by_mobile(self):
        return await self.begin()

    async def login_by_cookies(self):
        cookies = []
        for item in self.cookie_str.split(";"):
            if "=" not in item:
                continue
            name, value = item.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".google.com",
                    "path": "/",
                }
            )
        if cookies:
            await self.browser_context.add_cookies(cookies)
