# -*- coding: utf-8 -*-

import csv
from pathlib import Path

import config
from media_platform.google_maps.field import GOOGLE_MAPS_SHOP_OUTPUT_FIELDS
from media_platform.google_maps.help import (
    build_maps_search_url,
    build_tasks,
    load_points_from_csv,
    normalize_shop_state,
    parse_avg_price,
    parse_coordinates_from_url,
    parse_shop_id_from_url,
)
from model.m_google_maps import GoogleMapsPoint
from store.google_maps import GoogleMapsStoreFactory
from store.google_maps._store_impl import (
    GoogleMapsCsvStoreImplement,
    GoogleMapsDbStoreImplement,
    GoogleMapsJsonStoreImplement,
    GoogleMapsJsonlStoreImplement,
    GoogleMapsSqliteStoreImplement,
)


def test_load_points_from_csv_and_build_tasks(tmp_path: Path):
    csv_path = tmp_path / "points.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["city", "address", "country", "lat", "lng"])
        writer.writeheader()
        writer.writerow(
            {
                "city": "Itabira",
                "address": "Centro",
                "country": "BR",
                "lat": "-19.628",
                "lng": "-43.232",
            }
        )

    points = load_points_from_csv(csv_path)
    tasks = build_tasks(points, ["café", "bar"])

    assert len(points) == 1
    assert points[0].city == "Itabira"
    assert points[0].lat == -19.628
    assert len(tasks) == 2
    assert tasks[0].keyword == "café"
    assert tasks[0].task_id != tasks[1].task_id


def test_build_maps_search_url_uses_point_keyword_locale_and_zoom(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_MAPS_ZOOM", "20z")
    monkeypatch.setattr(config, "GOOGLE_MAPS_LOCALE", "pt-BR")
    point = GoogleMapsPoint(city="Itabira", country="BR", lat=-19.628, lng=-43.232)

    url = build_maps_search_url(point, "Refeição no local")

    assert url.startswith("https://www.google.com/maps/search/")
    assert "@-19.628,-43.232,20z" in url
    assert "hl=pt-BR" in url
    assert "Refei" in url


def test_parse_avg_price_samples():
    samples = {
        "BRL 100-120": ("R$", "100-120", ""),
        "Más de BRL 180": ("R$", "180+", ""),
        "R$60–100": ("R$", "60-100", ""),
        "+R$ 200": ("R$", "200+", ""),
        "BRL 50-60 K": ("R$", "50000-60000", ""),
        "$$$": ("", "", "$$$"),
        "": ("", "", ""),
    }

    for raw_value, expected in samples.items():
        assert parse_avg_price(raw_value) == expected


def test_parse_google_maps_url_helpers():
    url = (
        "https://www.google.com/maps/place/Foo/data=!4m7!3m6!"
        "1s0xa5a13caaf37b73:0x76a721cbf368abb3!8m2!"
        "3d-19.6301485!4d-43.2285471!16s%2Fg%2F11rft6x5mv!"
        "19sChIJc3vzqjyhpQARs6to88shp3Y?hl=pt-BR"
    )

    assert parse_shop_id_from_url(url) == "ChIJc3vzqjyhpQARs6to88shp3Y"
    assert parse_coordinates_from_url(url) == (-19.6301485, -43.2285471)


def test_normalize_shop_state_portuguese_cases():
    assert normalize_shop_state("Fechado · Abre às 18:00") == "正常营业"
    assert normalize_shop_state("Fechado permanentemente") == "永久闭店"
    assert normalize_shop_state("Temporariamente fechado") == "临时闭店"
    assert normalize_shop_state("Aberto agora") == "正常营业"


def test_google_maps_store_factory(monkeypatch):
    expected = {
        "csv": GoogleMapsCsvStoreImplement,
        "json": GoogleMapsJsonStoreImplement,
        "jsonl": GoogleMapsJsonlStoreImplement,
        "db": GoogleMapsDbStoreImplement,
        "postgres": GoogleMapsDbStoreImplement,
        "sqlite": GoogleMapsSqliteStoreImplement,
    }

    for save_option, store_class in expected.items():
        monkeypatch.setattr(config, "SAVE_DATA_OPTION", save_option)
        assert isinstance(GoogleMapsStoreFactory.create_store(), store_class)


def test_google_maps_output_fields_include_required_scheme_fields():
    required_fields = {
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
    }

    assert required_fields.issubset(set(GOOGLE_MAPS_SHOP_OUTPUT_FIELDS))
