# -*- coding: utf-8 -*-

import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from media_platform.google_maps.help import build_tasks, load_points_from_csv, resolve_points_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Google Maps plugin smoke check")
    parser.add_argument("--api-url", default="", help="Optional API base URL, such as http://127.0.0.1:8080")
    args = parser.parse_args()

    rows: list[tuple[str, str, str]] = []
    ok = True

    points_file = resolve_points_file()
    try:
        points = load_points_from_csv(points_file)
        tasks = build_tasks(points)
        rows.append(("points_file", "PASS", str(points_file)))
        rows.append(("points", "PASS" if points else "FAIL", str(len(points))))
        rows.append(("tasks", "PASS" if tasks else "FAIL", str(len(tasks))))
        ok = ok and bool(points) and bool(tasks)
    except Exception as exc:
        rows.append(("points/tasks", "FAIL", str(exc)))
        ok = False

    rows.extend(_sqlite_checks())

    if args.api_url:
        api_rows, api_ok = _api_checks(args.api_url.rstrip("/"))
        rows.extend(api_rows)
        ok = ok and api_ok

    _print_table(rows)
    return 0 if ok else 1


def _sqlite_checks() -> list[tuple[str, str, str]]:
    db_path = Path("database/sqlite_tables.db")
    if not db_path.exists():
        return [("sqlite", "WARN", f"not found: {db_path}")]

    tables = [
        "google_maps_points",
        "google_maps_tasks",
        "google_maps_shops",
        "google_maps_task_results",
        "google_maps_run_logs",
    ]
    rows: list[tuple[str, str, str]] = [("sqlite", "PASS", str(db_path))]
    try:
        con = sqlite3.connect(db_path)
        for table in tables:
            try:
                count = con.execute(f"select count(*) from {table}").fetchone()[0]
                rows.append((table, "PASS", str(count)))
            except sqlite3.Error as exc:
                rows.append((table, "FAIL", str(exc)))
        con.close()
    except sqlite3.Error as exc:
        rows.append(("sqlite", "FAIL", str(exc)))
    return rows


def _api_checks(api_url: str) -> tuple[list[tuple[str, str, str]], bool]:
    endpoints = [
        "/api/health",
        "/api/config/google-maps",
        "/api/google-maps/summary",
        "/api/google-maps/tasks/status",
        "/api/google-maps/report",
    ]
    rows: list[tuple[str, str, str]] = []
    ok = True
    for endpoint in endpoints:
        url = f"{api_url}{endpoint}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                rows.append((endpoint, "PASS", _summarize_payload(payload)))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            rows.append((endpoint, "FAIL", str(exc)))
            ok = False
    return rows, ok


def _summarize_payload(payload: dict) -> str:
    if "status" in payload and len(payload) == 1:
        return str(payload["status"])
    if "planned_tasks" in payload:
        return f"tasks={payload.get('planned_tasks')} shops={payload.get('db', {}).get('google_maps_shops', 0)}"
    if "counts" in payload:
        return f"shops={payload.get('counts', {}).get('google_maps_shops', 0)}"
    return ",".join(list(payload.keys())[:5])


def _print_table(rows: list[tuple[str, str, str]]) -> None:
    headers = ("check", "status", "detail")
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(3)
    ]
    print(f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  {headers[2]}")
    print(f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}")
    for check, status, detail in rows:
        print(f"{check:<{widths[0]}}  {status:<{widths[1]}}  {detail}")


if __name__ == "__main__":
    sys.exit(main())
