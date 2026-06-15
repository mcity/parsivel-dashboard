from app.models import ParsivelOTT

"""OTT Parsivel² class midpoints (Appendix C) and value decoding."""

# Class index → midpoint diameter (mm). Index 0 = class 1.
# Classes 1 and 2 are below the measurement range and are always empty.
DIAMETER_MID_MM: tuple[float, ...] = (
    0.062, 0.187, 0.312, 0.437, 0.562, 0.687, 0.812, 0.937,
    1.062, 1.187, 1.375, 1.625, 1.875, 2.125, 2.375, 2.750,
    3.250, 3.750, 4.250, 4.750, 5.500, 6.500, 7.500, 8.500,
    9.500, 11.000, 13.000, 15.000, 17.000, 19.000, 21.500, 24.500,
)

# Class index → midpoint fall velocity (m/s).
VELOCITY_MID_MS: tuple[float, ...] = (
    0.050, 0.150, 0.250, 0.350, 0.450, 0.550, 0.650, 0.750,
    0.850, 0.950, 1.100, 1.300, 1.500, 1.700, 1.900, 2.200,
    2.600, 3.000, 3.400, 3.800, 4.400, 5.200, 6.000, 6.800,
    7.600, 8.800, 10.400, 12.000, 13.600, 15.200, 17.600, 20.800,
)

NUM_CLASSES = 32

# Decoded text for parsivel_OTT.sensorStatus
SENSOR_STATUS_TEXT: dict[int, str] = {
    0: "OK",
    1: "screens dirty",
    2: "dirty/unusable",
    3: "laser damaged",
}

FILL_VALUE_FLOAT = -9.999
MOR_CLEAR_VALUE = 20000  # MORvisibility value indicating clear / no precip
RAIN_AMT_ROLLOVER_MM = 300.0  # rainAmt accumulator wraps back to 0 at this value
# Slack (mm) below the 300 rollover when deciding whether a negative ΔrainAmt is a
# genuine wrap vs. an accumulator reset: rainIntensity is a 1-minute average and
# can under-account the rain over the gap, so allow a few mm near the boundary.
WRAP_REACH_MARGIN_MM = 5.0

# Columns that can be filtered/sorted — maps name to the SQLAlchemy column.
FILTERABLE_COLUMNS = {
    "cpuTimestamp": ParsivelOTT.cpuTimestamp,
    "rainIntensity": ParsivelOTT.rainIntensity,
    "rainAmt": ParsivelOTT.rainAmt,
    "wxCode": ParsivelOTT.wxCode,
    "radarReflectivity": ParsivelOTT.radarReflectivity,
    "MORvisibility": ParsivelOTT.MORvisibility,
    "kineticEnergy": ParsivelOTT.kineticEnergy,
    "housingTemp": ParsivelOTT.housingTemp,
    "laserAmplitude": ParsivelOTT.laserAmplitude,
    "particleCount": ParsivelOTT.particleCount,
    "sensorStatus": ParsivelOTT.sensorStatus,
    "sensorSerNo": ParsivelOTT.sensorSerNo,
}

FILTER_OPS = {
    "eq": lambda col, val: col == val,
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
}

CSV_COLUMNS = [
    "cpuTimestamp", "sensorSerNo", "rainIntensity", "rainAmt", "wxCode",
    "radarReflectivity", "MORvisibility", "kineticEnergy", "housingTemp",
    "laserAmplitude", "particleCount", "sensorStatus", "sensorStatusText",
]

# WEATHER_CAT = 
#   if (code === null) return { label: "No data", color: "#616161" };
#   if (code === 0) return { label: "Clear", color: "#424242" };
#   if (code >= 51 && code <= 53) return { label: "Drizzle", color: "#90caf9" };
#   if (code >= 57 && code <= 58) return { label: "Drizzle with rain", color: "#4fc3f7" };
#   if (code >= 61 && code <= 63) return { label: "Rain", color: "#1e88e5" };
#   if (code >= 67 && code <= 68) return { label: "Rain/snow mix", color: "#7e57c2" };
#   if (code >= 71 && code <= 73) return { label: "Snow", color: "#e0e0e0" };
#   if (code === 77) return { label: "Snow grains", color: "#b0bec5" };
#   if (code >= 87 && code <= 88) return { label: "Soft hail", color: "#ff9800" };
#   if (code === 89) return { label: "Hail", color: "#ff5722" };
#   return { label: `Code ${code}`, color: "#757575" };
# }

WEATHER_CATEGORIES = [
    ("Clear",            (0, 0)),
    ("Drizzle",          (51, 53)),
    ("Drizzle with rain",(57, 58)),
    ("Rain",             (61, 63)),
    ("Rain/snow mix",    (67, 68)),
    ("Snow",             (71, 73)),
    ("Snow grains",      (77, 77)),
    ("Soft hail",        (87, 88)),
    ("Hail",             (89 ,89)),
]