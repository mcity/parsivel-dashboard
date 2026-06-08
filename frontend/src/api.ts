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
