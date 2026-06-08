"""Parsivel measurement endpoints."""

import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, request
from sqlalchemy import func, select

from app.db import get_session
from app.models import ParsivelOTT
from app.schemas import MeasurementOut, MeasurementPage

from app.constants import FILTERABLE_COLUMNS, FILTER_OPS, CSV_COLUMNS, MOR_CLEAR_VALUE

bp = Blueprint("measurements", __name__, url_prefix="/api")


def _parse_filter_value(col_name, raw):
    """Coerce a query-string value to the column's Python type."""
    col = FILTERABLE_COLUMNS[col_name]
    col_type = col.type.python_type
    if col_type is datetime:
        return datetime.fromisoformat(raw)
    return col_type(raw)


def _apply_filters(query, args):
    """Parse column__op=value params and add WHERE clauses."""
    for key, raw_value in args.items():
        if "__" not in key:
            continue
        col_name, op = key.rsplit("__", 1)
        if col_name not in FILTERABLE_COLUMNS or op not in FILTER_OPS:
            continue
        try:
            value = _parse_filter_value(col_name, raw_value)
        except (ValueError, TypeError):
            abort(400, description=f"Invalid value for {key}: {raw_value!r}")
        query = query.where(FILTER_OPS[op](FILTERABLE_COLUMNS[col_name], value))
    return query


def _apply_sort(query, sort_param):
    """Parse sort param: 'column' (asc) or '-column' (desc)."""
    if sort_param.startswith("-"):
        col_name = sort_param[1:]
        desc = True
    else:
        col_name = sort_param
        desc = False
    if col_name not in FILTERABLE_COLUMNS:
        abort(400, description=f"Cannot sort by unknown column: {col_name!r}")
    col = FILTERABLE_COLUMNS[col_name]
    return query.order_by(col.desc() if desc else col.asc())

# Build query based on filters and sorting
def _build_ott_query():
    """Parse request args and return (query, count_query, sort_param)."""
    start = request.args.get("start")
    end = request.args.get("end")
    sort_param = request.args.get("sort", "-cpuTimestamp")

    start_dt = None
    end_dt = None
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            abort(400, description=f"Invalid start datetime: {start!r}. Use ISO 8601 format.")
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            abort(400, description=f"Invalid end datetime: {end!r}. Use ISO 8601 format.")
    if start_dt and end_dt and start_dt > end_dt:
        abort(400, description="start must be before end")

    query = select(ParsivelOTT)
    count_query = select(func.count()).select_from(ParsivelOTT)

    if start_dt:
        query = query.where(ParsivelOTT.cpuTimestamp >= start_dt)
        count_query = count_query.where(ParsivelOTT.cpuTimestamp >= start_dt)
    if end_dt:
        query = query.where(ParsivelOTT.cpuTimestamp <= end_dt)
        count_query = count_query.where(ParsivelOTT.cpuTimestamp <= end_dt)

    query = _apply_filters(query, request.args)
    count_query = _apply_filters(count_query, request.args)

    return query, count_query, sort_param

# Endpoint: JSON get req return for latest measurement
@bp.get("/measurements/ott/latest")
def latest_ott():
    session = get_session()
    row = session.scalars(
        select(ParsivelOTT).order_by(ParsivelOTT.cpuTimestamp.desc()).limit(1)
    ).first()
    if row is None:
        abort(404, description="No rows found")
    return MeasurementOut.from_row(row).model_dump(mode="json")

# Endpoint: JSON get req return for display
@bp.get("/measurements/ott")
def list_ott():
    session = get_session()
    query, count_query, sort_param = _build_ott_query()

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    if page < 1:
        abort(400, description="page must be >= 1")
    if page_size < 1:
        abort(400, description="page_size must be >= 1")
    page_size = min(page_size, 1000)

    total = session.scalar(count_query)
    if total == 0:
        abort(404, description="No measurements found for the given filters")

    query = _apply_sort(query, sort_param)
    rows = session.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()

    if not rows:
        abort(404, description=f"Page {page} is out of range (total: {total})")

    return MeasurementPage(
        items=[MeasurementOut.from_row(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    ).model_dump(mode="json")

# Endpoint: CSV exporter from query
@bp.get("/measurements/ott/csv")
def export_ott_csv():
    session = get_session()
    query, count_query, sort_param = _build_ott_query()

    total = session.scalar(count_query)
    if total == 0:
        abort(404, description="No measurements found for the given filters")

    query = _apply_sort(query, sort_param)

    def generate():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        # Stream in chunks to keep memory flat
        chunk_size = 1000
        offset = 0
        while True:
            rows = session.scalars(
                query.offset(offset).limit(chunk_size)
            ).all()
            if not rows:
                break
            for row in rows:
                data = MeasurementOut.from_row(row).model_dump(mode="json")
                writer.writerow({col: data.get(col) for col in CSV_COLUMNS})
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            offset += chunk_size

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=measurements_ott.csv"},
    )
