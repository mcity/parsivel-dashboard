const BASE = "/api";

export interface Measurement {
  cpuTimestamp: string;
  sensorSerNo: string | null;
  rainIntensity: number | null;
  rainAmt: number | null;
  wxCode: number | null;
  radarReflectivity: number | null;
  MORvisibility: number | null;
  kineticEnergy: number | null;
  housingTemp: number | null;
  laserAmplitude: number | null;
  particleCount: number | null;
  sensorStatus: number | null;
  sensorStatusText: string | null;
}

export interface MeasurementPage {
  items: Measurement[];
  total: number;
  page: number;
  page_size: number;
}

export interface MeasurementParams {
  start?: string;
  end?: string;
  sort?: string;
  page?: number;
  page_size?: number;
  [key: string]: string | number | undefined; // column filters like rainIntensity__gte
}

// One aggregated time bucket for the hyetograph (see /measurements/ott/series).
export interface SeriesPoint {
  bucket: string;
  rainMm: number;
  peakIntensity: number | null;
  wxCode: number | null;
  cumulative: number;
}

export interface SeriesResponse {
  bucketSeconds: number;
  points: SeriesPoint[];
}

export interface SeriesParams {
  start?: string;
  end?: string;
  bucket?: number; // bucket width in seconds; omit to let the server auto-pick
  view?: "table" | "chart"; // "chart" enforces 1-year max on backend
}

export async function fetchSeries(params: SeriesParams = {}): Promise<SeriesResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }
  const res = await fetch(`${BASE}/measurements/ott/series?${query}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message ?? res.statusText);
  }
  return res.json();
}

export async function fetchMeasurements(
  params: MeasurementParams = {}
): Promise<MeasurementPage> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }
  const res = await fetch(`${BASE}/measurements/ott?${query}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message ?? res.statusText);
  }
  return res.json();
}

export async function fetchLatest(): Promise<Measurement> {
  const res = await fetch(`${BASE}/measurements/ott/latest`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.message ?? res.statusText);
  }
  return res.json();
}

export function buildCsvUrl(params: MeasurementParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (
      value !== undefined &&
      value !== "" &&
      key !== "page" &&
      key !== "page_size"
    ) {
      query.set(key, String(value));
    }
  }
  return `${BASE}/measurements/ott/csv?${query}`;
}
