"""SQLAlchemy ORM mappings for existing Parsivel tables (read-only).

The default SQL Server schema (usually `dbo`) is assumed; column types are best-guess
and should be verified against the live database. No DDL is emitted in production.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ParsivelOTT(Base):
    __tablename__ = "parsivel_OTT"

    # cpuTimestamp is the authoritative time axis; parsivelTime is unreliable.
    cpuTimestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    parsivelTime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sensorSerNo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rainIntensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainAmt: Mapped[float | None] = mapped_column(Float, nullable=True)
    wxCode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    radarReflectivity: Mapped[float | None] = mapped_column(Float, nullable=True)
    MORvisibility: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kineticEnergy: Mapped[float | None] = mapped_column(Float, nullable=True)
    housingTemp: Mapped[float | None] = mapped_column(Float, nullable=True)
    laserAmplitude: Mapped[int | None] = mapped_column(Integer, nullable=True)
    particleCount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensorStatus: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ParsivelAvgVed(Base):
    """Number-density spectrum per diameter class (telegram field 90).

    Units: log10(1/(m³·mm)). Fill value: -9.999.
    """
    __tablename__ = "parsivel_avg_ved"

    cpuTimestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    avg_ved_01: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_02: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_03: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_04: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_05: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_06: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_07: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_08: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_09: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_11: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_12: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_13: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_15: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_16: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_17: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_18: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_19: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_21: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_22: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_23: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_24: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_26: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_27: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_28: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_29: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_30: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_31: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ved_32: Mapped[float | None] = mapped_column(Float, nullable=True)


class ParsivelAvgPs(Base):
    """Average particle speed per diameter class (telegram field 91). Units m/s. Fill = 0."""
    __tablename__ = "parsivel_avg_ps"

    cpuTimestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    avg_ps_01: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_02: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_03: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_04: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_05: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_06: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_07: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_08: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_09: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_11: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_12: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_13: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_15: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_16: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_17: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_18: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_19: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_21: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_22: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_23: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_24: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_26: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_27: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_28: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_29: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_30: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_31: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ps_32: Mapped[float | None] = mapped_column(Float, nullable=True)
