// Human-readable explanations for each Parsivel² measurement field.
// Shared between the data table headers and the chart legend so the
// wording stays in one place.
export const columnTooltips = {
  cpuTimestamp: "Time the record was written by the logging PC. This is the reliable clock.",
  parsivelTime: "The sensor's own internal clock. Don't rely on it for timing.",
  parsivelReset: "When the sensor's accumulators were last reset. rainAmt counts up from this moment (except roll overs).",
  seqNo: "Internal tag for which telegram line the row came from (10/20/30/40), not a sequential counter.",
  sensorSerNo: "Serial number of the Parsivel² unit that produced this reading.",
  rainIntensity: "Rain rate (mm/h), averaged over the ~1-minute interval ending at this timestamp. 0 = no precipitation.",
  rainAmt: "Running total of rain (mm) accumulated since the last reset and rollover. Rolls over at 300 mm, not an instantaneous value.",
  wxCode: "Present-weather code (SYNOP wawa, Table 4680) for the interval. 0 = clear; 51-53 drizzle, 57-58 drizzle w/ rain, 61-63 rain, 67-68 rain/drizzle w/ snow, 71-73 snow, 77 snow grains, 87-88 soft hail, 89 hail.",
  radarReflectivity: "Equivalent radar reflectivity (dBZ) from the interval's drop-size distribution. -9.999 = no data / no precipitation.",
  MORvisibility: "Visibility in precipitation (m). 20000 = maximum range (clear / no precip).",
  kineticEnergy: "Kinetic energy of precipitation (J/m²h) over the interval, from drop sizes and speeds. Reflects rainfall erosivity.",
  housingTemp: "Instantaneous temperature inside the sensor housing (°C) at telegram time.",
  laserAmplitude: "Instantaneous laser-strip signal strength. ~22,000 is healthy; a downward trend warns of optics fouling before sensorStatus flips.",
  particleCount: "Particles detected and validated during the interval (since the previous timestamp), not instantaneous.",
  sensorStatus: "Optics/laser health at telegram time: 0 = OK, 1 = screens dirty (still measuring), 2 = dirty/unusable, 3 = laser fault.",
} as const;

export type ColumnTooltipKey = keyof typeof columnTooltips;

// Tooltips for chart series and filter controls (everything that isn't a
// table column). Kept here so all user-facing tooltip copy lives in one file.
export const uiTooltips = {
  chartFilters:
    "Column filters don't apply to the hyetograph, but do apply in the table view.",
  rainPerInterval:
    "Rainfall accumulated within each time bucket (mm), summed from the " +
    "sensor's rain accumulator with 300 mm roll-overs corrected.",
  cumulativeRain:
    "Running total of rainfall across the selected time range. " + columnTooltips.rainAmt,
  weatherType: columnTooltips.wxCode,
} as const;

// Time Range presets tooltip — composed with the live anchor timestamp.
export function timeRangeTooltip(latestLabel?: string): string {
  const anchor = latestLabel ? ` (${latestLabel})` : "";
  return (
    `Presets are measured back from the most recent available measurement${anchor}, ` +
    "not your current clock."
  );
}
