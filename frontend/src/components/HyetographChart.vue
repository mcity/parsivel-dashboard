<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import {
  Chart as ChartJS,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Title,
  Tooltip,
  Legend,
  Filler,
  type ChartData,
} from "chart.js";
import { Bar } from "vue-chartjs";
import "chartjs-adapter-date-fns";
import type { SeriesPoint } from "../api";
import { categoryForPoint } from "../weather";
import { uiTooltips } from "../tooltips";

ChartJS.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Title,
  Tooltip,
  Legend,
  Filler
);

const props = defineProps<{
  points: SeriesPoint[];
  bucketSeconds: number;
}>();

// Points arrive pre-sorted and pre-aggregated from the server.
const chartData = computed(() => {
  const data = props.points;

  return {
    labels: data.map((p) => p.bucket),
    datasets: [
      {
        type: "bar" as const,
        label: "Rain per interval (mm)",
        data: data.map((p) => p.rainMm),
        backgroundColor: "rgba(30, 136, 229, 0.7)",
        borderColor: "rgba(30, 136, 229, 1)",
        borderWidth: 1,
        yAxisID: "y",
        order: 2,
      },
      {
        type: "line" as const,
        label: "Cumulative Rain (mm)",
        data: data.map((p) => p.cumulative),
        borderColor: "rgba(255, 152, 0, 1)",
        backgroundColor: "rgba(255, 152, 0, 0.1)",
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        yAxisID: "y1",
        order: 1,
      },
    ],
    // Mixed bar + line chart: each dataset sets its own `type`, so cast to the
    // base bar ChartData that the <Bar> wrapper's data prop expects.
  } as ChartData<"bar">;
});

// Human-readable bucket width, e.g. "1 day", "15 minutes".
const bucketLabel = computed(() => {
  const s = props.bucketSeconds;
  if (!s) return "";
  const units: [number, string][] = [
    [604800, "week"],
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
    [1, "second"],
  ];
  for (const [size, name] of units) {
    if (s % size === 0) {
      const n = s / size;
      return `${n} ${name}${n > 1 ? "s" : ""}`;
    }
  }
  return `${s}s`;
});

// Custom HTML legend so each series can show an explanatory tooltip.
// Order matches the datasets defined in chartData above.
const chartRef = ref<any>(null);

const seriesMeta = [
  {
    label: "Rain per interval (mm)",
    color: "rgba(30, 136, 229, 1)",
    tooltip: uiTooltips.rainPerInterval,
  },
  {
    label: "Cumulative Rain (mm)",
    color: "rgba(255, 152, 0, 1)",
    tooltip: uiTooltips.cumulativeRain,
  },
];

const hidden = reactive(seriesMeta.map(() => false));

function toggleSeries(i: number) {
  const chart = chartRef.value?.chart;
  if (!chart) return;
  const nowVisible = !chart.isDatasetVisible(i);
  chart.setDatasetVisibility(i, nowVisible);
  hidden[i] = !nowVisible;
  chart.update();
}

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: "index" as const,
    intersect: false,
  },
  plugins: {
    // Replaced by the custom HTML legend below so each series can carry a tooltip.
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        title: (items: any[]) => {
          if (!items.length) return "";
          return new Date(items[0].label).toLocaleString();
        },
        // Both datasets (rain per interval + cumulative) render natively with
        // their color swatches; append peak intensity and weather as metadata.
        afterBody: (items: any[]) => {
          const p = items.length ? props.points[items[0].dataIndex] : undefined;
          if (!p) return [];
          const lines: string[] = [];
          if (p.peakIntensity != null) {
            lines.push(`Peak intensity: ${p.peakIntensity} mm/h`);
          }
          lines.push(`Weather: ${categoryForPoint(p).label}`);
          return lines;
        },
      },
      position: "nearest" as const,
    },
  },
  scales: {
    x: {
      type: "time" as const,
      time: {
        tooltipFormat: "PPpp",
        displayFormats: {
          minute: "MMM d yyyy HH:mm",
          hour: "MMM d yyyy HH:mm",
          day: "MMM d yyyy",
          week: "MMM d yyyy",
          month: "MMM yyyy",
        },
      },
      ticks: { color: "#aaa", maxRotation: 45 },
      grid: { color: "rgba(255,255,255,0.1)" },
    },
    y: {
      position: "left" as const,
      title: {
        display: true,
        text: "Rain per interval (mm)",
        color: "#aaa",
      },
      ticks: { color: "#aaa" },
      grid: { color: "rgba(255,255,255,0.1)" },
      beginAtZero: true,
    },
    y1: {
      position: "right" as const,
      title: {
        display: true,
        text: "Cumulative Rain (mm)",
        color: "#aaa",
      },
      ticks: { color: "#aaa" },
      grid: { drawOnChartArea: false },
      beginAtZero: true,
    },
  },
};
</script>

<template>
  <div class="hyetograph-container">
    <div class="custom-legend mb-1">
      <button
        v-for="(s, i) in seriesMeta"
        :key="s.label"
        type="button"
        class="legend-item text-caption"
        :class="{ 'legend-hidden': hidden[i] }"
        @click="toggleSeries(i)"
      >
        <span class="legend-swatch" :style="{ backgroundColor: s.color }" />
        {{ s.label }}
        <v-tooltip :text="s.tooltip" location="top" max-width="320">
          <template #activator="{ props }">
            <v-icon
              v-bind="props"
              icon="mdi-information-outline"
              size="x-small"
              class="ml-1 info-icon"
              @click.stop
            />
          </template>
        </v-tooltip>
      </button>
    </div>

    <div class="chart-area">
      <Bar ref="chartRef" :data="chartData" :options="chartOptions" />
    </div>

    <div v-if="bucketLabel" class="text-caption text-medium-emphasis text-center mt-1">
      Aggregated to {{ bucketLabel }} intervals
    </div>
  </div>
</template>

<style scoped>
.hyetograph-container {
  display: flex;
  flex-direction: column;
}
.custom-legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #ccc;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}
.legend-item.legend-hidden {
  opacity: 0.4;
  text-decoration: line-through;
}
.legend-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
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
  height: 380px;
}
</style>
