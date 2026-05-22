# -*- coding: utf-8 -*-

import asyncio
import re
from typing import Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractApiClient
from model.m_google_maps import GoogleMapsShop, GoogleMapsTask
from tools import utils

from .help import (
    build_maps_search_url,
    normalize_shop_state,
    parse_avg_price,
    parse_coordinates_from_url,
    parse_shop_id_from_url,
)


class GoogleMapsClient(AbstractApiClient):
    def __init__(self, page: Page):
        self.page = page

    async def request(self, method, url, **kwargs):
        return await self.page.request.fetch(url, method=method, **kwargs)

    async def update_cookies(self, browser_context: BrowserContext):
        return await browser_context.cookies([config.GOOGLE_MAPS_INDEX_URL])

    async def open_task_search(self, task: GoogleMapsTask) -> None:
        url = build_maps_search_url(task.point, task.keyword)
        utils.logger.info(
            f"[GoogleMapsClient.open_task_search] task={task.task_id} keyword={task.keyword} url={url}"
        )
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(2500)

    async def collect_result_links(self) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for _ in range(config.GOOGLE_MAPS_SCROLL_TIMES):
            page_links = await self.page.locator('a[href*="/maps/place/"]').evaluate_all(
                "(nodes) => nodes.map((node) => node.href).filter(Boolean)"
            )
            for link in page_links:
                if link not in seen:
                    seen.add(link)
                    links.append(link)
            if len(links) >= config.GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK:
                break
            await self._scroll_results()
            await asyncio.sleep(config.GOOGLE_MAPS_SCROLL_SLEEP_SEC)
        return links[: config.GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK]

    async def _scroll_results(self) -> None:
        candidates = [
            'div[role="feed"]',
            'div[aria-label][role="main"]',
            'div[role="region"]',
        ]
        for selector in candidates:
            locator = self.page.locator(selector).first
            if await locator.count():
                try:
                    await locator.evaluate("(node) => node.scrollBy(0, node.scrollHeight)")
                    return
                except Exception:
                    continue
        await self.page.mouse.wheel(0, 1800)

    async def extract_shop_from_url(self, task: GoogleMapsTask, detail_url: str) -> GoogleMapsShop:
        await self.page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(int(config.GOOGLE_MAPS_DETAIL_SLEEP_SEC * 1000))

        title = await self._text('h1')
        body_text = await self._body_text()
        dom_data = await self._dom_detail_data()
        current_url = self.page.url
        shop_id = parse_shop_id_from_url(current_url or detail_url)
        shop_lat, shop_lng = parse_coordinates_from_url(current_url or detail_url)
        level = self._parse_level(body_text)
        ratings = self._parse_rating_count(body_text)
        avg_price = self._parse_avg_price_text(body_text)
        currency_symbol, price_range, consumption_level = parse_avg_price(avg_price)
        is_open = self._parse_open_text(body_text)

        shop = GoogleMapsShop(
            keyword=[task.keyword],
            city=task.point.city,
            shop_id=shop_id,
            shop_name=title or self._parse_name_from_url(current_url or detail_url),
            level=level,
            category=dom_data.get("category") or self._parse_category(body_text),
            is_open=is_open,
            shop_lat=shop_lat,
            shop_lng=shop_lng,
            crawl_lat=task.point.lat,
            crawl_lng=task.point.lng,
            address=dom_data.get("address") or await self._button_text(["Endereço", "Address", "Direções"]),
            phone=dom_data.get("phone") or await self._button_text(["Telefone", "Phone"]),
            official_url=self._normalize_google_redirect_url(dom_data.get("official_url") or await self._website_url()),
            user_ratings_total=ratings,
            avg_price=avg_price,
            open_hours=dom_data.get("open_hours") or [],
            service_options=dom_data.get("service_options") or [],
            real_shop_state=normalize_shop_state(is_open),
            currency_symbol=currency_symbol,
            price_range=price_range,
            consumption_level=consumption_level,
            detail_url=current_url or detail_url,
        )
        return shop

    async def _text(self, selector: str) -> str:
        locator = self.page.locator(selector).first
        if await locator.count() == 0:
            return ""
        try:
            return (await locator.inner_text(timeout=3000)).strip()
        except Exception:
            return ""

    async def _body_text(self) -> str:
        try:
            return await self.page.locator("body").inner_text(timeout=5000)
        except Exception:
            return ""

    async def _button_text(self, labels: list[str]) -> str:
        for label in labels:
            locator = self.page.locator(f'button[aria-label*="{label}"], a[aria-label*="{label}"]').first
            if await locator.count() == 0:
                continue
            try:
                aria = await locator.get_attribute("aria-label")
                if aria:
                    return aria.replace(label, "").replace(":", "").strip()
                return (await locator.inner_text(timeout=2000)).strip()
            except Exception:
                continue
        return ""

    async def _website_url(self) -> str:
        locator = self.page.locator('a[data-item-id="authority"], a[aria-label*="Website"], a[aria-label*="Site"]').first
        if await locator.count() == 0:
            return ""

    async def _dom_detail_data(self) -> dict:
        script = r"""
        () => {
          const clean = (value) => (value || '').replace(/\s+/g, ' ').trim();
          const serviceTokens = ['Refeição no local', 'Para viagem', 'Entrega', 'Drive-through', 'Retirada', 'Delivery', 'Takeaway', 'Dine-in'];
          const controls = Array.from(document.querySelectorAll('button,a'));
          const byDataItem = (prefix) => controls.find((el) => (el.getAttribute('data-item-id') || '').startsWith(prefix));
          const byAria = (text) => controls.find((el) => (el.getAttribute('aria-label') || '').includes(text));
          const category = controls
            .filter((el) => (el.getAttribute('jsaction') || '').includes('.category'))
            .map((el) => clean(el.innerText))
            .filter(Boolean);
          const addressEl = byDataItem('address') || byAria('Endereço:') || byAria('Address:');
          const phoneEl = byDataItem('phone:') || byAria('Telefone:') || byAria('Phone:');
          const websiteEl = byDataItem('authority') || byAria('Website:') || byAria('Site:');
          const hourTexts = controls
            .map((el) => clean(el.getAttribute('aria-label') || ''))
            .filter((text) => text.includes('Copiar horário de funcionamento') || text.includes('Copy business hours'));
          const rawServiceTexts = Array.from(document.querySelectorAll('[aria-label], div, span'))
            .map((el) => clean(el.getAttribute('aria-label') || el.innerText || ''))
            .filter((text) => /Entrega|Retirada|Para viagem|Refeição no local|Drive-through|delivery|takeaway|dine-in/i.test(text))
            .filter((text, index, arr) => text.length <= 80 && arr.indexOf(text) === index)
            .slice(0, 12);
          const serviceTexts = serviceTokens.filter((token) => rawServiceTexts.some((text) => text.toLowerCase().includes(token.toLowerCase())));
          const address = clean(addressEl?.getAttribute('aria-label') || '').replace(/^Endereço:\s*/i, '').replace(/^Address:\s*/i, '');
          const phone = clean(phoneEl?.getAttribute('aria-label') || phoneEl?.innerText || '').replace(/^Telefone:\s*/i, '').replace(/^Phone:\s*/i, '');
          return {
            category,
            address,
            phone,
            official_url: websiteEl?.href || '',
            open_hours: hourTexts.map((text) => text.replace(/,\s*Copiar horário de funcionamento$/i, '').replace(/,\s*Copy business hours$/i, '')),
            service_options: serviceTexts
          };
        }
        """
        try:
            return await self.page.evaluate(script)
        except Exception:
            return {}
        try:
            return await locator.get_attribute("href") or ""
        except Exception:
            return ""

    @staticmethod
    def _parse_level(text: str) -> Optional[float]:
        match = re.search(r"\b([1-5][,.]\d)\b", text)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def _parse_rating_count(text: str) -> int:
        match = re.search(r"([\d.,]+)\s+(?:avaliações|reviews|comentários)", text, re.IGNORECASE)
        if not match:
            return 0
        return int(re.sub(r"\D", "", match.group(1)) or "0")

    @staticmethod
    def _parse_avg_price_text(text: str) -> str:
        patterns = [
            r"(?:BRL|R\$)\s*[\d\s]+(?:[-–]\s*[\d\s]+|\+)?(?:\s*K)?",
            r"Más de\s+(?:BRL|R\$)\s*[\d\s]+(?:\s*K)?",
            r"\${1,4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return ""

    @staticmethod
    def _parse_open_text(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            lower = line.lower()
            if any(token in lower for token in ["aberto", "fecha", "fechado", "cerrado", "open", "closed"]):
                return line
        return ""

    @staticmethod
    def _parse_category(text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        noise = {
            "rotas",
            "salvar",
            "salvos",
            "recentes",
            "próximo",
            "compartilhar",
            "ligar",
            "direções",
            "website",
            "site",
        }
        for line in lines[:20]:
            if 2 <= len(line) <= 80 and line.lower() not in noise and not re.search(r"\d", line):
                if not any(token in line.lower() for token in ["google", "maps"]):
                    return [line]
        return []

    @staticmethod
    def _normalize_google_redirect_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.path == "/url":
            target = parse_qs(parsed.query).get("q", [""])[0]
            return unquote(target)
        return url

    @staticmethod
    def _parse_name_from_url(url: str) -> str:
        match = re.search(r"/place/([^/]+)/", url)
        if not match:
            return ""
        return unquote(match.group(1)).replace("+", " ").strip()
