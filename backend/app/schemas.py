from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.constants import FILL_VALUE_FLOAT, SENSOR_STATUS_TEXT


def _nullify_fill(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value - FILL_VALUE_FLOAT) < 1e-6:
        return None
    return value


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cpuTimestamp: datetime
    sensorSerNo: str | None = None
    rainIntensity: float | None = None
    rainAmt: float | None = None
    wxCode: int | None = None
    radarReflectivity: float | None = None
    MORvisibility: int | None = None
    kineticEnergy: float | None = None
    housingTemp: float | None = None
    laserAmplitude: int | None = None
    particleCount: int | None = None
    sensorStatus: int | None = None
    sensorStatusText: str | None = None

    @classmethod
    def from_row(cls, row) -> "MeasurementOut":
        status = row.sensorStatus
        return cls(
            cpuTimestamp=row.cpuTimestamp,
            sensorSerNo=str(row.sensorSerNo) if row.sensorSerNo is not None else None,
            rainIntensity=_nullify_fill(row.rainIntensity),
            rainAmt=_nullify_fill(row.rainAmt),
            wxCode=row.wxCode,
            radarReflectivity=_nullify_fill(row.radarReflectivity),
            MORvisibility=row.MORvisibility,
            kineticEnergy=_nullify_fill(row.kineticEnergy),
            housingTemp=_nullify_fill(row.housingTemp),
            laserAmplitude=row.laserAmplitude,
            particleCount=row.particleCount,
            sensorStatus=status,
            sensorStatusText=SENSOR_STATUS_TEXT.get(status) if status is not None else None,
        )


class MeasurementPage(BaseModel):
    items: list[MeasurementOut]
    total: int
    page: int
    page_size: int


class HealthPoint(BaseModel):
    cpuTimestamp: datetime
    sensorStatus: int | None
    sensorStatusText: str | None
    laserAmplitude: int | None
    particleCount: int | None
