# -*- coding: utf-8 -*-

import config
from base.base_crawler import AbstractStore
from media_platform.google_maps.help import ensure_shop_defaults
from model.m_google_maps import GoogleMapsShop
from tools import utils

from ._store_impl import (
    GoogleMapsCsvStoreImplement,
    GoogleMapsDbStoreImplement,
    GoogleMapsJsonStoreImplement,
    GoogleMapsJsonlStoreImplement,
    GoogleMapsSqliteStoreImplement,
)


class GoogleMapsStoreFactory:
    STORES = {
        "csv": GoogleMapsCsvStoreImplement,
        "json": GoogleMapsJsonStoreImplement,
        "jsonl": GoogleMapsJsonlStoreImplement,
        "db": GoogleMapsDbStoreImplement,
        "postgres": GoogleMapsDbStoreImplement,
        "sqlite": GoogleMapsSqliteStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = GoogleMapsStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[GoogleMapsStoreFactory.create_store] Invalid save option. "
                "Supported: csv, json, jsonl, db, sqlite, postgres"
            )
        return store_class()


async def update_google_maps_shop(shop: GoogleMapsShop, task_id: str = "", task_keyword: str = ""):
    save_item = ensure_shop_defaults(shop)
    save_item["last_modify_ts"] = utils.get_current_timestamp()
    save_item["_task_id"] = task_id
    save_item["_task_keyword"] = task_keyword
    utils.logger.info(
        f"[store.google_maps.update_google_maps_shop] shop_id={save_item.get('shop_id')} name={save_item.get('shop_name')}"
    )
    await GoogleMapsStoreFactory.create_store().store_content(save_item)


async def update_google_maps_task(task_item: dict):
    store = GoogleMapsStoreFactory.create_store()
    if hasattr(store, "store_task"):
        await store.store_task(task_item)


async def get_google_maps_task_status(task_id: str) -> str:
    store = GoogleMapsStoreFactory.create_store()
    if hasattr(store, "get_task_status"):
        return await store.get_task_status(task_id)
    return ""


async def sync_google_maps_points_and_tasks(points: list[dict], tasks: list[dict]):
    store = GoogleMapsStoreFactory.create_store()
    if hasattr(store, "sync_points_and_tasks"):
        await store.sync_points_and_tasks(points, tasks)
