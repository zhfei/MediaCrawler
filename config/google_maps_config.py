# -*- coding: utf-8 -*-

import os

# Google Maps platform configuration
GOOGLE_MAPS_PLATFORM_NAME = "google_maps"
GOOGLE_MAPS_TARGET_PLATFORM = "GoogleMap"
GOOGLE_MAPS_COUNTRY = "BR"
GOOGLE_MAPS_LOCALE = "pt-BR"
GOOGLE_MAPS_TIMEZONE = "America/Sao_Paulo"
GOOGLE_MAPS_ZOOM = "20z"
GOOGLE_MAPS_INDEX_URL = "https://www.google.com/maps"
GOOGLE_MAPS_USE_SYSTEM_CHROME = os.getenv("GOOGLE_MAPS_USE_SYSTEM_CHROME", "true").lower() in {
    "1",
    "true",
    "yes",
}
GOOGLE_MAPS_CHROME_EXECUTABLE_PATH = os.getenv(
    "GOOGLE_MAPS_CHROME_EXECUTABLE_PATH",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

# Run MediaCrawler from the MediaCrawler directory; the source CSV lives in the
# parent project directory for this task.
GOOGLE_MAPS_POINTS_FILE = os.getenv(
    "GOOGLE_MAPS_POINTS_FILE",
    "../谷歌巴西-采集点位_test(1).csv",
)

GOOGLE_MAPS_KEYWORDS = [
    "café",
    "bar",
    "padaria",
    "sobremesa",
    "suco",
    "takeaway",
    "delivery",
    "restaurante",
    "pizza",
    "hambúrguer",
    "espeto",
    "pão",
    "lanches",
    "sucos",
    "Hamburgueria",
    "Pizzaria",
    "Lanchonete",
    "Sanduicheria",
    "dinner-in",
    "Refeição no local",
    "Entrega",
    "Drive-through",
    "Doceria",
    "Loja de bolos",
    "Sorveteria",
]

# 0 means execute all generated tasks. Keep a small default to prevent accidental
# large Google Maps runs during local validation.
GOOGLE_MAPS_TASK_LIMIT = int(os.getenv("GOOGLE_MAPS_TASK_LIMIT", "1"))
GOOGLE_MAPS_SCROLL_TIMES = int(os.getenv("GOOGLE_MAPS_SCROLL_TIMES", "8"))
GOOGLE_MAPS_SCROLL_SLEEP_SEC = float(os.getenv("GOOGLE_MAPS_SCROLL_SLEEP_SEC", "1.2"))
GOOGLE_MAPS_DETAIL_SLEEP_SEC = float(os.getenv("GOOGLE_MAPS_DETAIL_SLEEP_SEC", "1.0"))
GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK = int(os.getenv("GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK", "20"))
GOOGLE_MAPS_SCREENSHOT_ON_ERROR = os.getenv("GOOGLE_MAPS_SCREENSHOT_ON_ERROR", "true").lower() in {
    "1",
    "true",
    "yes",
}
