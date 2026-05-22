# -*- coding: utf-8 -*-

from enum import Enum


class GoogleMapsTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class GoogleMapsShopState(str, Enum):
    SUSPECT_CLOSED = "疑似闭店"
    TEMPORARILY_CLOSED = "临时闭店"
    PERMANENTLY_CLOSED = "永久闭店"
    NORMAL = "正常营业"


GOOGLE_MAPS_SHOP_OUTPUT_FIELDS = [
    "keyword",
    "platform",
    "city",
    "shop_id",
    "shop_name",
    "level",
    "category",
    "is_open",
    "shop_lat",
    "shop_lng",
    "crawl_lat",
    "crawl_lng",
    "address",
    "phone",
    "order_url",
    "official_url",
    "user_ratings_total",
    "avg_price",
    "open_hours",
    "report_count",
    "menu_url",
    "service_options",
    "busy_time",
    "create_time",
    "real_shop_state",
    "currency_symbol",
    "price_range",
    "consumption_level",
    "detail_url",
]
