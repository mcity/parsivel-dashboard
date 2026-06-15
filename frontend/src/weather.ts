// Shared weather-type categorization for the hyetograph and distribution charts.
//
// OTT Parsivel² present-weather type follows SYNOP Table 4680 (precipitation
// codes). The sensor emits a sparse, specific set of codes — not the full 0–99
// range — so each branch matches the exact groups in Table 4680.
import type { SeriesPoint } from "./api";

export interface WxCategory {
  label: string;
  color: string;
}

export function getWxCategory(code: number | null): WxCategory {
  if (code === null) return { label: "No data", color: "#616161" };
  if (code === 0) return { label: "Clear", color: "#424242" };
  if (code >= 51 && code <= 53) return { label: "Drizzle", color: "#90caf9" };
  if (code >= 57 && code <= 58) return { label: "Drizzle with rain", color: "#4fc3f7" };
  if (code >= 61 && code <= 63) return { label: "Rain", color: "#1e88e5" };
  if (code >= 67 && code <= 68) return { label: "Rain/snow mix", color: "#7e57c2" };
  if (code >= 71 && code <= 73) return { label: "Snow", color: "#e0e0e0" };
  if (code === 77) return { label: "Snow grains", color: "#b0bec5" };
  if (code >= 87 && code <= 88) return { label: "Soft hail", color: "#ff9800" };
  if (code === 89) return { label: "Hail", color: "#ff5722" };
  return { label: `Code ${code}`, color: "#757575" };
}

export function categoryForPoint(p: SeriesPoint): WxCategory {
  return getWxCategory(p.wxCode);
}

const CATEGORY_COLORS: Record<string, string> = Object.fromEntries(
  [0, 51, 57, 61, 67, 71, 77, 87, 89].map(code => {
    const { label, color } = getWxCategory(code);
    return [label, color];
  })
);
CATEGORY_COLORS["Precipitation (corrected)"] = "#00897b";

export function colorForLabel(label: string): string {
  return CATEGORY_COLORS[label] ?? "#757575";
}
