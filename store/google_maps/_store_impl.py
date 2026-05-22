# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path
from typing import Dict

import aiofiles
from sqlalchemy import select

import config
from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import (
    GoogleMapsPoint as GoogleMapsPointModel,
    GoogleMapsRunLog,
    GoogleMapsShop as GoogleMapsShopModel,
    GoogleMapsTask as GoogleMapsTaskModel,
    GoogleMapsTaskResult,
)
from media_platform.google_maps.field import GOOGLE_MAPS_SHOP_OUTPUT_FIELDS
from tools import utils


def _data_dir(file_type: str) -> Path:
    if config.SAVE_DATA_PATH:
        base_path = Path(config.SAVE_DATA_PATH) / "google_maps" / file_type
    else:
        base_path = Path("data") / "google_maps" / file_type
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def _without_internal_fields(content_item: Dict) -> Dict:
    return {key: value for key, value in content_item.items() if not key.startswith("_")}


def _only_output_fields(content_item: Dict) -> Dict:
    return {key: content_item.get(key, "" if key not in {"keyword", "category", "open_hours", "service_options"} else []) for key in GOOGLE_MAPS_SHOP_OUTPUT_FIELDS}


def _serialize_collection_fields(content_item: Dict) -> Dict:
    item = dict(content_item)
    for key in ("keyword", "category", "open_hours", "service_options"):
        value = item.get(key)
        if isinstance(value, str):
            continue
        item[key] = json.dumps(value or [], ensure_ascii=False)
    return item


class GoogleMapsCsvStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        content_item = _serialize_collection_fields(_only_output_fields(_without_internal_fields(content_item)))
        file_path = _data_dir("csv") / f"search_shops_{utils.get_current_date()}.csv"
        file_exists = file_path.exists()
        with file_path.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=GOOGLE_MAPS_SHOP_OUTPUT_FIELDS)
            if not file_exists or file.tell() == 0:
                writer.writeheader()
            writer.writerow({key: content_item.get(key, "") for key in GOOGLE_MAPS_SHOP_OUTPUT_FIELDS})

    async def store_comment(self, comment_item: Dict):
        return None

    async def store_creator(self, creator: Dict):
        return None


class GoogleMapsJsonlStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        content_item = _only_output_fields(_without_internal_fields(content_item))
        file_path = _data_dir("jsonl") / f"search_shops_{utils.get_current_date()}.jsonl"
        async with aiofiles.open(file_path, "a", encoding="utf-8") as file:
            await file.write(json.dumps(content_item, ensure_ascii=False) + "\n")

    async def store_comment(self, comment_item: Dict):
        return None

    async def store_creator(self, creator: Dict):
        return None


class GoogleMapsJsonStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        content_item = _only_output_fields(_without_internal_fields(content_item))
        file_path = _data_dir("json") / f"search_shops_{utils.get_current_date()}.json"
        existing = []
        if file_path.exists() and file_path.stat().st_size > 0:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
                try:
                    existing = json.loads(await file.read())
                except json.JSONDecodeError:
                    existing = []
        existing.append(content_item)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(json.dumps(existing, ensure_ascii=False, indent=2))

    async def store_comment(self, comment_item: Dict):
        return None

    async def store_creator(self, creator: Dict):
        return None


class GoogleMapsDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        shop_id = content_item.get("shop_id")
        if not shop_id:
            return

        now_ts = utils.get_current_timestamp()
        async with get_session() as session:
            task_id = content_item.pop("_task_id", "")
            keyword = content_item.pop("_task_keyword", "")
            content_item = _serialize_collection_fields(content_item)
            stmt = select(GoogleMapsShopModel).where(GoogleMapsShopModel.shop_id == shop_id)
            res = await session.execute(stmt)
            db_shop = res.scalar_one_or_none()
            if db_shop:
                content_item = self._merge_existing_shop(db_shop, content_item)
                content_item["report_count"] = (db_shop.report_count or 0) + 1
                content_item["last_modify_ts"] = now_ts
                for key, value in content_item.items():
                    if hasattr(db_shop, key):
                        setattr(db_shop, key, value)
            else:
                content_item["add_ts"] = now_ts
                content_item["last_modify_ts"] = now_ts
                session.add(GoogleMapsShopModel(**content_item))

            if task_id and keyword:
                await self._save_task_result(session, task_id, shop_id, keyword, now_ts)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        return None

    async def store_creator(self, creator: Dict):
        return None

    async def store_task(self, task_item: Dict):
        now_ts = utils.get_current_timestamp()
        async with get_session() as session:
            stmt = select(GoogleMapsTaskModel).where(GoogleMapsTaskModel.task_id == task_item["task_id"])
            res = await session.execute(stmt)
            db_task = res.scalar_one_or_none()
            if db_task:
                for key, value in task_item.items():
                    if hasattr(db_task, key):
                        setattr(db_task, key, value)
                db_task.last_modify_ts = now_ts
            else:
                task_item["add_ts"] = now_ts
                task_item["last_modify_ts"] = now_ts
                session.add(GoogleMapsTaskModel(**task_item))
            await session.commit()

    async def get_task_status(self, task_id: str) -> str:
        async with get_session() as session:
            stmt = select(GoogleMapsTaskModel.status).where(GoogleMapsTaskModel.task_id == task_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none() or ""

    async def sync_points_and_tasks(self, points: list[Dict], tasks: list[Dict]):
        now_ts = utils.get_current_timestamp()
        async with get_session() as session:
            existing_points = {
                (row.country, row.city, row.lat, row.lng)
                for row in (await session.execute(select(GoogleMapsPointModel))).scalars().all()
            }
            for point in points:
                key = (point["country"], point["city"], point["lat"], point["lng"])
                if key not in existing_points:
                    session.add(
                        GoogleMapsPointModel(
                            city=point["city"],
                            address=point.get("address", ""),
                            country=point["country"],
                            lat=point["lat"],
                            lng=point["lng"],
                            add_ts=now_ts,
                            last_modify_ts=now_ts,
                        )
                    )
                    existing_points.add(key)

            existing_task_ids = {
                task_id
                for task_id in (await session.execute(select(GoogleMapsTaskModel.task_id))).scalars().all()
            }
            for task in tasks:
                if task["task_id"] in existing_task_ids:
                    continue
                task["add_ts"] = now_ts
                task["last_modify_ts"] = now_ts
                session.add(GoogleMapsTaskModel(**task))
            await session.commit()

    async def store_run_log(self, log_item: Dict):
        now_ts = utils.get_current_timestamp()
        async with get_session() as session:
            session.add(
                GoogleMapsRunLog(
                    task_id=log_item.get("task_id", ""),
                    level=log_item.get("level", "info"),
                    message=log_item.get("message", ""),
                    screenshot_path=log_item.get("screenshot_path", ""),
                    add_ts=now_ts,
                )
            )
            await session.commit()

    @staticmethod
    def _merge_existing_shop(db_shop: GoogleMapsShopModel, incoming: Dict) -> Dict:
        try:
            existing_keywords = set(json.loads(db_shop.keyword or "[]"))
        except json.JSONDecodeError:
            existing_keywords = set()
        try:
            incoming_keywords = set(json.loads(incoming.get("keyword") or "[]"))
        except json.JSONDecodeError:
            incoming_keywords = set()
        incoming["keyword"] = json.dumps(sorted(existing_keywords | incoming_keywords), ensure_ascii=False)
        return incoming

    @staticmethod
    async def _save_task_result(session, task_id: str, shop_id: str, keyword: str, now_ts: int):
        stmt = select(GoogleMapsTaskResult).where(
            GoogleMapsTaskResult.task_id == task_id,
            GoogleMapsTaskResult.shop_id == shop_id,
        )
        res = await session.execute(stmt)
        exists = res.scalar_one_or_none()
        if not exists:
            session.add(
                GoogleMapsTaskResult(
                    task_id=task_id,
                    shop_id=shop_id,
                    keyword=keyword,
                    add_ts=now_ts,
                    last_modify_ts=now_ts,
                )
            )


class GoogleMapsSqliteStoreImplement(GoogleMapsDbStoreImplement):
    pass
