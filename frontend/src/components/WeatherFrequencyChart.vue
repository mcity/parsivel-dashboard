<script setup lang="ts">
import { computed } from "vue";
import {
  Chart as ChartJS,
  BarController,
  BarElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "vue-chartjs";
import type { SeriesPoint } from "../api";
import { categoryForPoint } from "../weather";
import { uiTooltips } from "../tooltips";

ChartJS.register(
  BarController,
  BarElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend
);

const props = defineProps<{
  points: SeriesPoint[];
  bucketSeconds: number;
}>();

// Time spent in each weather category. Each bucket covers `bucketSeconds` of
// elapsed time, so weighting by bucket width gives a zoom-invariant duration
// rather than a raw bucket count (which would swing wildly with the server's
// auto-chosen bucket size).
const weatherDuration = computed(() => {
  const totals = new Map<string, { seconds: number; color: string }>();
  for (const p of props.points) {
    const cat = categoryForPoint(p);
    if (!totals.has(cat.label)) {
      totals.set(cat.label, { seconds: 0, color: cat.color });
    }
    totals.get(cat.label)!.seconds += props.bucketSeconds;
  }
  return Array.from(totals.entries())
    .sort((a, b) => b[1].seconds - a[1].seconds)
    .map(([label, data]) => ({
      label,
      seconds: data.seconds,
      hours: data.seconds / 3600,
      color: data.color,
    }));
});

// Compact, human-readable duration for the tooltip: "3d 4h", "5h 30m", "45m".
function formatDuration(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d) parts.push(`${d}d`);
  if (h) parts.push(`${h}h`);
  if (m && !d) parts.push(`${m}m`);
  return parts.length ? parts.join(" ") : `${seconds}s`;
}

const chartData = computed(() => ({
  labels: weatherDuration.value.map((w) => w.label),
  datasets: [
    {
      label: "Time",
      data: weatherDuration.value.map((w) => w.hours),
      backgroundColor: weatherDuration.value.map((w) => w.color),
      borderColor: weatherDuration.value.map((w) => w.color),
      borderWidth: 1,
    },
  ],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: "y" as const,
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        // Show a friendly duration ("2d 5h") instead of the raw hours value.
        label: (item: any) => {
          const w = weatherDuration.value[item.dataIndex];
          return w ? formatDuration(w.seconds) : "";
        },
      },
    },
  },
  scales: {
    x: {
      beginAtZero: true,
      title: { display: true, text: "Hours", color: "#aaa" },
      ticks: { color: "#aaa" },
      grid: { color: "rgba(255,255,255,0.1)" },
    },
    y: {
      ticks: { color: "#aaa" },
      grid: { color: "rgba(255,255,255,0.1)" },
    },
  },
};
</script>

<template>
  <div class="weather-frequency-container">
    <div class="text-caption text-medium-emphasis mb-2 d-inline-flex align-center">
      Weather Type Distribution
      <v-tooltip :text="uiTooltips.weatherType" location="top" max-width="320">
        <template #activator="{ props }">
          <v-icon
            v-bind="props"
            icon="mdi-information-outline"
            size="x-small"
            class="ml-1 info-icon"
          />
        </template>
      </v-tooltip>
    </div>
    <div class="chart-area">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<style scoped>
.weather-frequency-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.info-icon {
  opacity: 0.6;
  cursor: help;
}
.info-icon:hover {
  opacity: 1;
}
.chart-area {
  position: relative;
  height: 300px;
}
</style>
