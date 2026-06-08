"""Test fixtures: in-memory SQLite + Flask test client."""

import os
from datetime import datetime, timedelta

import pytest

# Must be set before importing the app — config reads DATABASE_URL at instantiation.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
from app.models import Base, ParsivelOTT


@pytest.fixture()
def engine():
    # StaticPool + check_same_thread keep one shared connection so seeded data
    # is visible across threads (Flask test client + setup).
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def seeded(session_factory):
    s = session_factory()
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    s.add_all([
        ParsivelOTT(
            cpuTimestamp=t0,
            sensorSerNo="ABC123",
            rainIntensity=0.5,
            rainAmt=0.05,
            wxCode=51,
            radarReflectivity=12.3,
            MORvisibility=5000,
            kineticEnergy=1.2,
            housingTemp=18.5,
            laserAmplitude=22050,
            particleCount=42,
            sensorStatus=0,
        ),
        ParsivelOTT(
            cpuTimestamp=t0 + timedelta(minutes=1),
            sensorSerNo="ABC123",
            rainIntensity=-9.999,  # fill -> nulled in response
            rainAmt=0.05,
            wxCode=0,
            radarReflectivity=-9.999,
            MORvisibility=20000,
            kineticEnergy=0.0,
            housingTemp=18.6,
            laserAmplitude=22040,
            particleCount=0,
            sensorStatus=1,
        ),
    ])
    s.commit()
    s.close()


@pytest.fixture()
def app(session_factory, seeded):
    flask_app = create_app()
    flask_app.config.update(TESTING=True, SESSION_FACTORY=session_factory)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
