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
import { uiTooltips } from "../tooltips";
import type { WeatherCategory } from "../api";
import { colorForLabel } from "../weather";

ChartJS.register(
  BarController,
  BarElement,
  LinearScale,
  CategoryScale,
  Title,
  Tooltip,
  Legend
);

const props = defineProps<{ categories: WeatherCategory[] }>();

// Compact, human-readable duration for the tooltip: "years, months, days, hours, minutes".
const UNITS: [string, number][] = [["y",525600],["mo",43200],["d",1440],["h",60],["m",1]];
function formatDuration(minutes: number): string {
  let rem = Math.round(minutes);
  const parts: string[] = [];
  for (const [name, size] of UNITS) {
    const n = Math.floor(rem / size);
    if (n) { parts.push(`${n}${name}`); rem -= n * size; }
  }
  return parts.length ? parts.slice(0, 2).join(" ") : "0m";  // top 2 units
}

const chartData = computed(() => ({
  labels: props.categories.map(c => c.label),
  datasets: [
    {
      label: "Time",
      data: props.categories.map(c => c.minutes / 60 / 24),
      backgroundColor: props.categories.map(c => colorForLabel(c.label)),
      borderColor: props.categories.map(c => colorForLabel(c.label)),
      borderWidth: 1,
    },
  ],
}));

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: "y" as const,
  interaction: {
    mode: "index" as const,   // resolve by category row, not the bar shape
    intersect: false,         // don't require hovering the (tiny) bar itself
    axis: "y" as const,       // pick the row by vertical position (horizontal bars)
  },
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      callbacks: {
        // Show a readable duration ("2d 5h") instead of minute values.
        label: (item: any) => {
          const w = props.categories[item.dataIndex]; 
          return w ? formatDuration(w.minutes) : ""
        },
      },
    },
  },
  scales: {
    x: {
      beginAtZero: true,
      title: { display: true, text: "Days", color: "#aaa" },
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
