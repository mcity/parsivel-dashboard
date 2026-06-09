# parsivel-dashboard

Flask REST template for a read-only viewer over an existing OTT Parsivel²
disdrometer database (SQL Server). The Parsivel-specific table mappings,
class-midpoint constants, and response schemas are wired up; routes are left
as a single placeholder so this can serve as a starting point.

The frontend is not built yet.

## Layout

```
parsivel-dashboard/
├── backend/
│   ├── app/
│   │   ├── __init__.py       # Flask create_app() factory
│   │   ├── config.py         # Settings from env (DATABASE_URL, CORS_ORIGINS)
│   │   ├── db.py             # SQLAlchemy engine + per-request session
│   │   ├── constants.py      # OTT class midpoints, sensor-status text, fill values
│   │   ├── models.py         # ORM mapping for existing tables (read-only)
│   │   ├── schemas.py        # Pydantic response models (fill -> null)
│   │   └── routes/
│   │       └── example.py    # placeholder route: GET /api/example
│   ├── tests/                # pytest, uses in-memory SQLite
│   ├── wsgi.py               # gunicorn entrypoint
│   ├── pyproject.toml
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## What's in the template

Already wired:

- Flask app factory (`app/__init__.py`) with CORS and per-request DB session teardown.
- SQLAlchemy 2.0 engine + `sessionmaker`, with a `SESSION_FACTORY` config hook for tests.
- Pydantic-based settings (`DATABASE_URL`, `CORS_ORIGINS`) loaded from `.env`.
- ORM mappings for `parsivel_OTT`, `parsivel_avg_ved`, `parsivel_avg_ps`.
- Pydantic response schemas with fill-value (`-9.999`) nulling and decoded
  sensor-status text.
- One placeholder route — `GET /api/example` — showing the pattern
  blueprint → session → model → schema → JSON.
- Health probe at `GET /api/ping`.
- pytest setup with in-memory SQLite via `StaticPool`, plus a working
  integration test against the placeholder route.

Not provided (intentionally — extend as needed):

- Real business endpoints (measurements list, latest, health timeline, etc.).
- Auth.
- Frontend.

## Mapped tables (read-only)

| Table | Purpose |
|---|---|
| `parsivel_OTT` | One row per measurement (rain intensity, reflectivity, sensor status, …) |
| `parsivel_avg_ved` | Number-density per diameter class (telegram field 90) |
| `parsivel_avg_ps` | Average particle speed per diameter class (field 91) |

`cpuTimestamp` is the authoritative time axis everywhere; `parsivelTime` is
ignored because that clock is often unset.

The column types in `app/models.py` are best-guess. Verify against the live
database before going to production. The default SQL Server schema (`dbo`) is
assumed — if the login uses a different default schema, add
`__table_args__ = {"schema": "dbo"}` to each model.

## Local dev (without Docker)

Prereqs: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Microsoft ODBC
Driver 18 for SQL Server installed on the host.

```bash
cp .env.example .env
# edit .env: set DATABASE_URL to your SQL Server instance

cd backend
C:\Users\WWICGAA\.local\bin\uv.exe sync
runas /netonly /user:UMROOT\billhong cmd
cd C:\Users\WWICGAA\Documents\parsivel-dashboard\backend
C:\Users\WWICGAA\.local\bin\uv.exe run flask --app wsgi run --debug --port 8000

# seperate terminal
cd frontend
npm run dev
# visit http://localhost:5173


The server listens on `http://localhost:8000`.

## Docker

The provided Dockerfile installs ODBC Driver 18 inside the image, so you only
need Docker on the host. Production server is gunicorn.

```bash
cp .env.example .env
# edit .env

docker compose up --build
```

The compose file mounts `./backend` and runs gunicorn with `--reload` for dev.

## Environment variables

| Var | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL, e.g. `mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes` |
| `CORS_ORIGINS` | Optional comma-separated origin list for the future frontend (e.g. `http://localhost:5173`) |

Secrets must live in `.env` (never committed) or be injected by the
orchestrator. The app is strictly read-only and runs no schema migrations.

## Tests

```bash
cd backend
uv run pytest
```

Tests use an in-memory SQLite database via a `SESSION_FACTORY` override on the
Flask app config — no SQL Server needed. `pyodbc` is still installed as a
runtime dependency.

## Adding a real route

Follow the pattern in `app/routes/example.py`:

```python
from flask import Blueprint
from sqlalchemy import select
from app.db import get_session
from app.models import ParsivelOTT
from app.schemas import MeasurementOut

bp = Blueprint("measurements", __name__, url_prefix="/api/measurements")


@bp.get("/latest")
def latest():
    session = get_session()
    row = session.scalars(
        select(ParsivelOTT).order_by(ParsivelOTT.cpuTimestamp.desc()).limit(1)
    ).first()
    if row is None:
        return {"error": "no rows"}, 404
    return MeasurementOut.from_row(row).model_dump(mode="json")
```

Then register the blueprint in `app/__init__.py`:

```python
from app.routes import measurements
app.register_blueprint(measurements.bp)
```
