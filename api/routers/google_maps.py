# -*- coding: utf-8 -*-

import sqlite3
import csv
import io
import json
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Body, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

import config
from media_platform.google_maps.field import GOOGLE_MAPS_SHOP_OUTPUT_FIELDS
from media_platform.google_maps.help import build_tasks, load_points_from_csv, resolve_points_file

router = APIRouter(prefix="/google-maps", tags=["google-maps"])


class GoogleMapsTaskResetRequest(BaseModel):
    status: str = Field(default="failed", description="要重置的任务状态，默认 failed")
    limit: int = Field(default=0, ge=0, description="最多重置多少条，0 表示不限制")


@router.get("/summary")
async def google_maps_summary():
    points = load_points_from_csv(resolve_points_file())
    tasks = build_tasks(points)
    db_counts = _sqlite_counts()
    return {
        "points_file": str(resolve_points_file()),
        "points": len(points),
        "keywords": len(config.GOOGLE_MAPS_KEYWORDS),
        "planned_tasks": len(tasks),
        "task_limit": config.GOOGLE_MAPS_TASK_LIMIT,
        "max_result_links_per_task": config.GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK,
        "max_retry_times": config.GOOGLE_MAPS_MAX_RETRY_TIMES,
        "db": db_counts,
    }


@router.post("/points/upload")
async def google_maps_points_upload(
    body: bytes = Body(...),
    x_filename: str = Header(default="points.csv"),
):
    """Upload a local points CSV selected in browser and return server-side path."""
    filename = _safe_csv_filename(x_filename)
    upload_dir = Path("data/google_maps/input")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(body)

    points = load_points_from_csv(file_path)
    tasks = build_tasks(points)
    return {
        "success": True,
        "filename": filename,
        "points_file": str(file_path),
        "points": len(points),
        "planned_tasks": len(tasks),
    }


@router.get("/tasks/preview")
async def google_maps_tasks_preview(limit: int = 20, points_file: str = ""):
    """Preview generated point-keyword tasks without starting the crawler."""
    source_file = points_file or resolve_points_file()
    points = load_points_from_csv(source_file)
    tasks = build_tasks(points)
    safe_limit = max(1, min(limit, 200))
    return {
        "points_file": str(source_file),
        "total": len(tasks),
        "limit": safe_limit,
        "items": [
            {
                "task_id": task.task_id,
                "city": task.point.city,
                "country": task.point.country,
                "crawl_lat": task.point.lat,
                "crawl_lng": task.point.lng,
                "keyword": task.keyword,
            }
            for task in tasks[:safe_limit]
        ],
    }


@router.get("/tasks/status")
async def google_maps_tasks_status():
    """Return SQLite task status counts for breakpoint/resume inspection."""
    return {
        "db_path": str(_sqlite_db_path()),
        "status": _sqlite_status_counts(),
    }


@router.get("/shops")
async def google_maps_shops(limit: int = 100, offset: int = 0, keyword: str = ""):
    """Return Google Maps shops from SQLite with normalized array fields."""
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    rows, total = _sqlite_shop_rows(safe_limit, safe_offset, keyword)
    return {
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "items": rows,
    }


@router.get("/report")
async def google_maps_report():
    """Return collection progress and aggregation report."""
    return {
        "points_file": str(resolve_points_file()),
        "task_status": _sqlite_status_counts(),
        "counts": _sqlite_counts(),
        "top_keywords": _sqlite_group_counts("google_maps_task_results", "keyword", 20),
        "top_categories": _sqlite_json_array_counts("google_maps_shops", "category", 20),
        "shop_states": _sqlite_group_counts("google_maps_shops", "real_shop_state", 20),
        "cities": _sqlite_group_counts("google_maps_shops", "city", 20),
    }


@router.get("/run-logs")
async def google_maps_run_logs(limit: int = 100):
    """Return persisted Google Maps run logs from SQLite."""
    safe_limit = max(1, min(limit, 500))
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return {"items": []}
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select task_id, level, message, screenshot_path, add_ts "
            "from google_maps_run_logs order by id desc limit ?",
            (safe_limit,),
        ).fetchall()
        con.close()
        return {"items": [dict(row) for row in rows]}
    except sqlite3.Error:
        return {"items": []}


@router.get("/export")
async def google_maps_export(file_type: str = "csv", limit: int = 0):
    """Export SQLite Google Maps shops as CSV or JSON."""
    rows, total = _sqlite_shop_rows(limit if limit > 0 else 1000000, 0, "")
    filename = f"google_maps_shops_{total}.{file_type}"
    if file_type == "json":
        return Response(
            content=json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if file_type != "csv":
        return {
            "success": False,
            "message": f"Unsupported file_type: {file_type}",
            "allowed_file_type": ["csv", "json"],
        }

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GOOGLE_MAPS_SHOP_OUTPUT_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: json.dumps(row.get(field, []), ensure_ascii=False)
                if field in {"keyword", "category", "open_hours", "service_options"}
                else row.get(field, "")
                for field in GOOGLE_MAPS_SHOP_OUTPUT_FIELDS
            }
        )
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tasks/reset")
async def google_maps_tasks_reset(payload: GoogleMapsTaskResetRequest):
    """Reset failed/running tasks back to pending so they can be retried."""
    allowed_status = {"pending", "running", "success", "failed"}
    if payload.status not in allowed_status:
        return {
            "success": False,
            "message": f"Unsupported status: {payload.status}",
            "allowed_status": sorted(allowed_status),
        }

    db_path = _sqlite_db_path()
    if not db_path.exists():
        return {"success": False, "message": f"SQLite database not found: {db_path}"}

    try:
        con = sqlite3.connect(db_path)
        if payload.limit > 0:
            task_ids = [
                row[0]
                for row in con.execute(
                    "select task_id from google_maps_tasks where status = ? limit ?",
                    (payload.status, payload.limit),
                ).fetchall()
            ]
            if task_ids:
                con.executemany(
                    "update google_maps_tasks set status = 'pending', last_error = '' where task_id = ?",
                    [(task_id,) for task_id in task_ids],
                )
            changed = len(task_ids)
        else:
            cur = con.execute(
                "update google_maps_tasks set status = 'pending', last_error = '' where status = ?",
                (payload.status,),
            )
            changed = cur.rowcount
        con.commit()
        con.close()
        return {"success": True, "reset_status": payload.status, "changed": changed}
    except sqlite3.Error as exc:
        return {"success": False, "message": str(exc)}


def _sqlite_counts() -> dict:
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return {}
    tables = [
        "google_maps_points",
        "google_maps_tasks",
        "google_maps_shops",
        "google_maps_task_results",
        "google_maps_run_logs",
    ]
    counts = {}
    try:
        con = sqlite3.connect(db_path)
        for table in tables:
            try:
                counts[table] = con.execute(f"select count(*) from {table}").fetchone()[0]
            except sqlite3.Error:
                counts[table] = 0
        con.close()
    except sqlite3.Error:
        return {}
    return counts


def _sqlite_status_counts() -> dict:
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return {}
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "select status, count(*) from google_maps_tasks group by status order by status"
        ).fetchall()
        con.close()
        return {status or "unknown": count for status, count in rows}
    except sqlite3.Error:
        return {}


def _sqlite_shop_rows(limit: int, offset: int, keyword: str) -> tuple[list[dict], int]:
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return [], 0

    where = ""
    params: list = []
    if keyword:
        where = "where keyword like ?"
        params.append(f"%{keyword}%")

    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        total = con.execute(f"select count(*) from google_maps_shops {where}", params).fetchone()[0]
        rows = con.execute(
            f"select {', '.join(GOOGLE_MAPS_SHOP_OUTPUT_FIELDS)} from google_maps_shops "
            f"{where} order by id desc limit ? offset ?",
            [*params, limit, offset],
        ).fetchall()
        con.close()
        return [_normalize_shop_row(dict(row)) for row in rows], total
    except sqlite3.Error:
        return [], 0


def _normalize_shop_row(row: dict) -> dict:
    for field in ("keyword", "category", "open_hours", "service_options"):
        value = row.get(field)
        if isinstance(value, str):
            try:
                row[field] = json.loads(value) if value else []
            except json.JSONDecodeError:
                row[field] = [value] if value else []
    return row


def _sqlite_group_counts(table: str, field: str, limit: int) -> list[dict]:
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return []
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            f"select {field}, count(*) as count from {table} "
            f"where {field} is not null and {field} != '' "
            f"group by {field} order by count desc limit ?",
            (limit,),
        ).fetchall()
        con.close()
        return [{"name": name, "count": count} for name, count in rows]
    except sqlite3.Error:
        return []


def _sqlite_json_array_counts(table: str, field: str, limit: int) -> list[dict]:
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return []
    counts: dict[str, int] = {}
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(f"select {field} from {table} where {field} is not null and {field} != ''").fetchall()
        con.close()
        for (raw_value,) in rows:
            try:
                values = json.loads(raw_value)
            except (TypeError, json.JSONDecodeError):
                values = [raw_value]
            if not isinstance(values, list):
                values = [values]
            for value in values:
                name = str(value).strip()
                if name:
                    counts[name] = counts.get(name, 0) + 1
    except sqlite3.Error:
        return []
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _sqlite_db_path() -> Path:
    return Path("database/sqlite_tables.db")


def _safe_csv_filename(filename: str) -> str:
    name = Path(unquote(filename or "points.csv")).name
    for token in ("/", "\\", ":", "\x00"):
        name = name.replace(token, "_")
    if not name.lower().endswith(".csv"):
        name = f"{name}.csv"
    return name
