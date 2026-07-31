# parsivel-dashboard

A read-only dashboard for an OTT Parsivel² laser disdrometer. The sensor is
outside the UMTRI building. It records one measurement each minute.

The backend reads an existing SQL Server database with Flask and SQLAlchemy. It
does not write to the database, and it runs no migrations. The frontend is a Vue
3 and Vuetify application. It shows a landing page, a table of the measurements,
a hyetograph, and a weather-type chart. You can also export the rows as CSV.

## Stack

**Backend** — Python 3.12 or later, with [uv](https://docs.astral.sh/uv/) for
the packages.

| Part | Tool |
|---|---|
| Web framework | Flask 3 |
| ORM | SQLAlchemy 2.0 |
| Database | Microsoft SQL Server, through pyodbc and ODBC Driver 18 |
| Validation and settings | Pydantic 2, pydantic-settings |
| Cross-origin requests | Flask-CORS |
| Production server | gunicorn |
| Tests | pytest, with SQLite in memory |

**Frontend** — Node.js 24 or later, with npm.

| Part | Tool |
|---|---|
| Framework | Vue 3 (Composition API, `<script setup>`) |
| Language | TypeScript |
| Component library | Vuetify 4 |
| Icons | Material Design Icons (`@mdi/font`) |
| Routing | Vue Router 4 |
| Charts | Chart.js 4, through vue-chartjs, with the date-fns adapter |
| Build tool | Vite 8 |
| Type checks | vue-tsc |

The project uses no CSS framework. All the styles come from Vuetify and from
scoped CSS in the components.

## Layout

```
parsivel-dashboard/
├── backend/
│   ├── app/
│   │   ├── __init__.py        # Flask create_app() factory
│   │   ├── config.py          # Settings from .env
│   │   ├── db.py              # Engine and per-request session
│   │   ├── constants.py       # Class midpoints, status text, filter maps
│   │   ├── models.py          # ORM mapping for the three tables
│   │   ├── schemas.py         # Pydantic response models
│   │   └── routes/
│   │       └── measurements.py  # All /api endpoints
│   ├── tests/                 # pytest, with in-memory SQLite
│   ├── wsgi.py                # gunicorn entrypoint
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   └── src/
│       ├── api.ts             # Typed calls to the backend
│       ├── router/            # "/" landing page, "/dashboard" the data
│       ├── views/             # LandingPage, NotFound
│       └── components/        # Table, charts, landing-page parts
├── docker-compose.yml
└── README.md
```

<!-- ## Tables

The app reads three tables. `cpuTimestamp` is the time axis in all of them. Do
not use `parsivelTime`, because that clock is frequently wrong.

| Table | Contents |
|---|---|
| `parsivel_OTT` | One row for each measurement: rain rate, rain total, weather code, reflectivity, visibility, kinetic energy, housing temperature, laser amplitude, particle count, and sensor status. |
| `parsivel_avg_ved` | Number density for each of the 32 diameter classes (telegram field 90). Unit: log10(1/(m³·mm)). Fill value: -9.999. |
| `parsivel_avg_ps` | Average particle speed for each of the 32 diameter classes (telegram field 91). Unit: m/s. Fill value: 0. |

The column types in `app/models.py` are estimates. Compare them with the live
database before you go to production. The app assumes the default SQL Server
schema (`dbo`). If your login uses a different schema, add
`__table_args__ = {"schema": "dbo"}` to each model. -->

## Setup

You must have Python 3.12 or later, [uv](https://docs.astral.sh/uv/), Node.js 24
or later, and Microsoft ODBC Driver 18 for SQL Server.

### 1. Make the environment file

Write a file `.env` in the root of the project:

```
DATABASE_URL= ...
CORS_ORIGINS=http://localhost:5173
```

Keep the secrets in `.env`. Do not commit this file.

### 2. Start the backend

```bash
cd backend
uv sync
uv run flask --app wsgi run --debug --port 8000
```

The backend listens on `http://localhost:8000`.

If SQL Server uses Windows authentication, first start a shell with your domain
account. Then run the two commands above in that shell.

```
runas /netonly /user:UMROOT\<user> cmd
```

### 3. Start the frontend

Use a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite sends all `/api` requests to port 8000, thus
the backend must run at the same time.

## Tests

```bash
cd backend
uv run pytest
```

The tests use an in-memory SQLite database through a `SESSION_FACTORY` override
on the Flask config. You do not need SQL Server to run them.

## Docker

The Dockerfile installs ODBC Driver 18 in the image, and gunicorn serves the
app. The compose file starts the **backend only**. Start the frontend with
`npm run dev`.

```bash
docker compose up --build
```

## Deployment

See [DEPLOY.md](DEPLOY.md) for the demo deployment: a one-time snapshot of the
database into SQLite (`backend/scripts/snapshot_to_sqlite.py`), a single
production image that serves both the API and the built frontend (root
`Dockerfile` + `docker-compose.prod.yml`), and the steps to run it on an EC2
instance.
