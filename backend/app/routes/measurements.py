"""Parsivel measurement endpoints."""

import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, request
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.types import DateTime, Integer

from app.constants import (
    CSV_COLUMNS,
    FILL_VALUE_FLOAT,
    FILTER_OPS,
    FILTERABLE_COLUMNS,
    RAIN_AMT_ROLLOVER_MM,
    SENSOR_STATUS_TEXT,
    WEATHER_CATEGORIES,
    WRAP_REACH_MARGIN_MM,
)
from app.db import get_session
from app.models import ParsivelOTT
from app.schemas import (
    MeasurementOut,
    MeasurementPage,
    SeriesOut,
    SeriesPoint,
    _nullify_fill,
)

bp = Blueprint("measurements", __name__, url_prefix="/api")


# --- Time-bucketing (dialect-aware) ---------------------------------------
# Floors a datetime column to the start of an N-second bucket. The expression
# differs by backend (SQL Server in prod, SQLite in tests), so we compile it
# per dialect instead of writing portable-but-impossible SQL.
class _TimeBucket(ColumnElement):
    type = DateTime()
    inherit_cache = False  # bucket size is inlined into SQL; don't share cache entries

    def __init__(self, col, bucket_seconds: int):
        self.col = col
        self.bucket_seconds = int(bucket_seconds)


@compiles(_TimeBucket, "mssql")
def _compile_bucket_mssql(element, compiler, **kw):
    col = compiler.process(element.col, **kw)
    n = element.bucket_seconds
    # Anchor at 2000-01-01 so DATEDIFF(SECOND, ...) stays within int range.
    return (
        f"DATEADD(SECOND, (DATEDIFF(SECOND, '2000-01-01', {col}) / {n}) * {n}, "
        f"'2000-01-01')"
    )


@compiles(_TimeBucket, "sqlite")
def _compile_bucket_sqlite(element, compiler, **kw):
    col = compiler.process(element.col, **kw)
    n = element.bucket_seconds
    return f"datetime((CAST(strftime('%s', {col}) AS INTEGER) / {n}) * {n}, 'unixepoch')"


@compiles(_TimeBucket)
def _compile_bucket_default(element, compiler, **kw):
    # Unknown dialect: fall back to no bucketing (each row is its own bucket).
    return compiler.process(element.col, **kw)


# Seconds since a fixed epoch. Used only via subtraction (gap between two rows),
# so the dialect-specific epoch anchor cancels out.
class _EpochSeconds(ColumnElement):
    type = Integer()
    inherit_cache = True

    def __init__(self, col):
        self.col = col


@compiles(_EpochSeconds, "mssql")
def _compile_epoch_mssql(element, compiler, **kw):
    return f"DATEDIFF(SECOND, '2000-01-01', {compiler.process(element.col, **kw)})"


@compiles(_EpochSeconds, "sqlite")
def _compile_epoch_sqlite(element, compiler, **kw):
    return f"CAST(strftime('%s', {compiler.process(element.col, **kw)}) AS INTEGER)"


@compiles(_EpochSeconds)
def _compile_epoch_default(element, compiler, **kw):
    raise NotImplementedError("_EpochSeconds: unsupported dialect")


# Bucket widths (seconds) we'll snap to, smallest first. We pick the smallest
# bucket that keeps the point count near SERIES_TARGET_POINTS for the range.
BUCKET_LADDER_SECONDS = (
    60, 300, 600, 900, 1800, 3600, 10800, 21600, 43200, 86400, 604800,
)
SERIES_TARGET_POINTS = 600


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

def _parse_iso(value, field):
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Invalid {field} datetime: {value!r}. Use ISO 8601 format.")


def _parse_time_bounds():
    """Parse start/end query args into datetimes (or None), validating order."""
    start = request.args.get("start")
    end = request.args.get("end")
    start_dt = _parse_iso(start, "start") if start else None
    end_dt = _parse_iso(end, "end") if end else None
    if start_dt and end_dt and start_dt > end_dt:
        abort(400, description="start must be before end")
    return start_dt, end_dt


# Build query based on filters and sorting
def _build_ott_query():
    """Parse request args and return (query, count_query, sort_param)."""
    sort_param = request.args.get("sort", "-cpuTimestamp")
    start_dt, end_dt = _parse_time_bounds()

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


def _resolve_bucket(start_dt, end_dt, override):
    """Pick a bucket width (seconds): explicit override, else auto from range."""
    if override is not None:
        try:
            n = int(override)
        except (TypeError, ValueError):
            abort(400, description=f"Invalid bucket seconds: {override!r}")
        if n < 1:
            abort(400, description="bucket must be >= 1 second")
        return n
    span = max((end_dt - start_dt).total_seconds(), 1.0)
    ideal = span / SERIES_TARGET_POINTS
    for width in BUCKET_LADDER_SECONDS:
        if width >= ideal:
            return width
    return BUCKET_LADDER_SECONDS[-1]


def _series_query(start_dt, end_dt, bucket_seconds):
    """Time-bucketed rainfall aggregate, computed entirely in the database.

    rainMm per bucket is the sum of consecutive ΔrainAmt. A negative step is
    treated as a 300 mm accumulator wrap *only* when the rain rate over the gap
    could plausibly have driven the accumulator past 300
    (prev_amt + intensity * gap_hours >= 300 - margin); otherwise it's an
    accumulator reset and contributes nothing. The first sample in the window
    has no predecessor, so it contributes nothing.
    """
    ts = ParsivelOTT.cpuTimestamp
    bucket = _TimeBucket(ts, bucket_seconds).label("bucket")
    prev_amt = func.lag(ParsivelOTT.rainAmt).over(order_by=ts)
    # Seconds since the previous sample (epoch anchor cancels in the subtraction).
    epoch = _EpochSeconds(ts)
    gap_seconds = epoch - func.lag(epoch).over(order_by=ts)
    eff_intensity = ParsivelOTT.rainIntensity

    base = (
        select(
            bucket,
            ParsivelOTT.rainIntensity.label("intensity"),
            ParsivelOTT.wxCode.label("wx"),
            (ParsivelOTT.rainAmt - prev_amt).label("raw_delta"),
            # Highest the accumulator could have reached over the gap: if it
            # clears 300, a wrap was physically possible.
            (prev_amt + eff_intensity * gap_seconds / 3600.0).label("reach"),
        )
        .where(ParsivelOTT.cpuTimestamp >= start_dt)
        .where(ParsivelOTT.cpuTimestamp <= end_dt)
        .where(ParsivelOTT.rainAmt.is_not(None))
        .cte("base")
    )

    corrected = case(
        (base.c.raw_delta >= 0, base.c.raw_delta),  # normal accumulation
        # Negative step that could have reached 300 => genuine wrap; add it back.
        (
            base.c.reach >= RAIN_AMT_ROLLOVER_MM - WRAP_REACH_MARGIN_MM,
            base.c.raw_delta + RAIN_AMT_ROLLOVER_MM,
        ),
        else_=0.0,  # negative but unreachable => accumulator reset; ignore.
    )

    agg = (
        select(
            base.c.bucket.label("bucket"),
            func.sum(corrected).label("rain_mm"),
            func.max(base.c.intensity).label("peak_intensity"),
            func.max(base.c.wx).label("wx_code"),  # higher SYNOP code ~ more severe
        )
        .group_by(base.c.bucket)
        .cte("agg")
    )

    return (
        select(
            agg.c.bucket,
            agg.c.rain_mm,
            agg.c.peak_intensity,
            agg.c.wx_code,
            func.sum(agg.c.rain_mm).over(order_by=agg.c.bucket).label("cumulative"),
        )
        .order_by(agg.c.bucket)
    )
    
def _count(session, *predicates) -> int:
    q = select(func.count()).select_from(ParsivelOTT).where(*predicates)
    return session.scalar(q) or 0

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

# Endpoint: time-bucketed rainfall series for the hyetograph
@bp.get("/measurements/ott/series")
def series_ott():
    session = get_session()
    start_dt, end_dt = _parse_time_bounds()

    # Missing bound(s) ("All") -> span the full data extent (cheap, indexed).
    if start_dt is None or end_dt is None:
        lo, hi = session.execute(
            select(func.min(ParsivelOTT.cpuTimestamp), func.max(ParsivelOTT.cpuTimestamp))
        ).one()
        start_dt = start_dt or lo
        end_dt = end_dt or hi

    # Empty table -> empty series (200), so the chart degrades gracefully.
    if start_dt is None or end_dt is None:
        return SeriesOut(bucketSeconds=0, points=[]).model_dump(mode="json")

    # Chart view has a 1-year (366-day) limit for one year (366 b/c leap year).
    if start_dt and end_dt:
        span_days = (end_dt - start_dt).days
        if span_days > 366:
            abort(400, description=f"Chart view: time range ({span_days} days) exceeds 1 year maximum. Narrow the date range to load the chart.")

    bucket_seconds = _resolve_bucket(start_dt, end_dt, request.args.get("bucket"))
    rows = session.execute(_series_query(start_dt, end_dt, bucket_seconds)).all()

    points = [
        SeriesPoint(
            bucket=r.bucket,
            rainMm=round(float(r.rain_mm or 0.0), 5),
            peakIntensity=(
                round(peak, 5)
                if (peak := _nullify_fill(r.peak_intensity)) is not None
                else None
            ),
            wxCode=r.wx_code,
            cumulative=round(float(r.cumulative or 0.0), 5),
        )
        for r in rows
    ]
    return SeriesOut(bucketSeconds=bucket_seconds, points=points).model_dump(mode="json")

# Endpoint: time-bucketed weather code distr. graph
@bp.get("/measurements/ott/weather")
def weather_distr_ott():
    session = get_session()
    start_dt, end_dt = _parse_time_bounds() 
    
    results = []
    
    for name, bounds in WEATHER_CATEGORIES:
        
        # filter based on time and bounds of current category
        filters = [ParsivelOTT.wxCode.between(bounds[0], bounds[1])]
        if start_dt: 
            filters.append(ParsivelOTT.cpuTimestamp >= start_dt)
        if end_dt:   
            filters.append(ParsivelOTT.cpuTimestamp <= end_dt)
        
        minutes = _count(session, *filters)
        
        # corrected_percip_min = None
        
        # # add corrected percip if there is any
        # if name == "Clear":
        #     corrected_percip_min = 0
        #     PRECIP = ParsivelOTT.rainIntensity > 0
        #     corrected_percip_min = _count(session, *filters, PRECIP)  # clear-coded but raining
        #     minutes -= corrected_percip_min                            # actually clear
                
        results.append({"label": name, "minutes": minutes})
        
        # if corrected_percip_min is not None:
        #     results.append({
        #         "label": "Precipitation (corrected)",
        #         "minutes": corrected_percip_min,
        #     })
        
    return {"categories": results}

# Endpoint: when the deployed copy of the data was last synced from SQL Server.
# The sync job (scripts/ingest.py) appends to `_sync_log`; when the API reads
# SQL Server directly there is no such table, and lastSyncAt is null.
@bp.get("/sync/status")
def sync_status():
    session = get_session()
    try:
        row = session.execute(
            text("SELECT synced_at, rows_inserted FROM _sync_log ORDER BY id DESC LIMIT 1")
        ).first()
    except DBAPIError:
        session.rollback()
        row = None
    if row is None:
        return {"lastSyncAt": None, "rowsInserted": None}
    return {"lastSyncAt": row[0], "rowsInserted": row[1]}


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

        # Stream in large chunks, skipping Pydantic model conversion for speed.
        # Columns that need fill-value nulling (see _nullify_fill).
        float_cols = {"rainIntensity", "rainAmt", "radarReflectivity", "kineticEnergy", "housingTemp"}

        chunk_size = 50000
        offset = 0
        while True:
            rows = session.scalars(
                query.offset(offset).limit(chunk_size)
            ).all()
            if not rows:
                break
            for row in rows:
                # Build dict directly from row attributes; skip Pydantic to avoid per-row overhead.
                data = {}
                for col in CSV_COLUMNS:
                    val = getattr(row, col, None)
                    # Nullify fill values for float columns.
                    if col in float_cols and val is not None:
                        if abs(val - FILL_VALUE_FLOAT) < 1e-6:
                            val = None
                    # Decode sensorStatus to text.
                    elif col == "sensorStatusText":
                        status = getattr(row, "sensorStatus", None)
                        val = SENSOR_STATUS_TEXT.get(status) if status is not None else None
                    data[col] = val
                writer.writerow(data)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            offset += chunk_size

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=measurements_ott.csv"},
    )
