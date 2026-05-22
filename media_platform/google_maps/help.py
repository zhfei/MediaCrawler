# -*- coding: utf-8 -*-

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import config
from model.m_google_maps import GoogleMapsPoint, GoogleMapsShop, GoogleMapsTask


CURRENCY_MAP = {
    "BRL": "R$",
    "R$": "R$",
}


def resolve_points_file() -> Path:
    path = Path(config.GOOGLE_MAPS_POINTS_FILE)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def load_points_from_csv(csv_path: str | Path | None = None) -> list[GoogleMapsPoint]:
    path = Path(csv_path) if csv_path else resolve_points_file()
    if not path.exists():
        raise FileNotFoundError(f"Google Maps points CSV not found: {path}")

    points: list[GoogleMapsPoint] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            city = (row.get("city") or "").strip()
            country = (row.get("country") or config.GOOGLE_MAPS_COUNTRY).strip()
            if not city or not country:
                continue
            try:
                lat = float(row.get("lat") or "")
                lng = float(row.get("lng") or "")
            except ValueError:
                continue
            points.append(
                GoogleMapsPoint(
                    city=city,
                    address=(row.get("address") or "").strip(),
                    country=country,
                    lat=lat,
                    lng=lng,
                )
            )
    return points


def build_task_id(point: GoogleMapsPoint, keyword: str) -> str:
    raw = f"{point.country}|{point.city}|{point.lat:.6f}|{point.lng:.6f}|{keyword}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_tasks(points: list[GoogleMapsPoint], keywords: list[str] | None = None) -> list[GoogleMapsTask]:
    task_keywords = keywords or list(config.GOOGLE_MAPS_KEYWORDS)
    tasks: list[GoogleMapsTask] = []
    for point in points:
        for keyword in task_keywords:
            tasks.append(
                GoogleMapsTask(
                    task_id=build_task_id(point, keyword),
                    point=point,
                    keyword=keyword,
                )
            )
    return tasks


def build_maps_search_url(point: GoogleMapsPoint, keyword: str) -> str:
    search = quote(keyword)
    return (
        f"{config.GOOGLE_MAPS_INDEX_URL}/search/{search}/"
        f"@{point.lat},{point.lng},{config.GOOGLE_MAPS_ZOOM}?hl={config.GOOGLE_MAPS_LOCALE}"
    )


def parse_avg_price(value: str) -> tuple[str, str, str]:
    text = (value or "").strip()
    if not text:
        return "", "", ""

    normalized = text.replace("–", "-").replace("â€“", "-").replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized)

    if re.fullmatch(r"\${1,4}", normalized):
        return "", "", normalized

    currency_symbol = ""
    for token, symbol in CURRENCY_MAP.items():
        if token in normalized:
            currency_symbol = symbol
            break

    has_plus = "Más de" in normalized or "+" in normalized
    amount_text = normalized.replace("Más de", "").replace("BRL", "").replace("R$", "").replace("+", "")
    numbers = re.findall(r"\d+", amount_text)

    if "K" in normalized.upper():
        numbers = [str(int(number) * 1000) for number in numbers]

    if len(numbers) >= 2:
        price_range = f"{numbers[0]}-{numbers[1]}"
    elif len(numbers) == 1:
        price_range = f"{numbers[0]}+" if has_plus else numbers[0]
    else:
        price_range = ""

    return currency_symbol, price_range, ""


def parse_shop_id_from_url(url: str) -> str:
    if not url:
        return ""
    patterns = [
        r"ChI[a-zA-Z0-9_-]+",
        r"place_id:([a-zA-Z0-9_-]+)",
        r"!1s([^!]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def parse_coordinates_from_url(url: str) -> tuple[float | None, float | None]:
    match = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", url)
    if match:
        return float(match.group(1)), float(match.group(2))
    match = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


def normalize_shop_state(open_text: str) -> str:
    text = (open_text or "").lower()
    if "permanentemente" in text or "permanently" in text:
        return "永久闭店"
    if "temporariamente" in text or "temporarily" in text:
        return "临时闭店"
    if ("fechado" in text or "cerrado" in text or "closed" in text) and not any(
        token in text for token in ["abre", "opens", "abre às", "abre a las"]
    ):
        return "疑似闭店"
    return "正常营业"


def ensure_shop_defaults(shop: GoogleMapsShop) -> dict:
    data = shop.model_dump()
    if not data.get("create_time"):
        data["create_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data
