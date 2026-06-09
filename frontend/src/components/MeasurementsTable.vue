<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from "vue";
import {
  fetchMeasurements,
  buildCsvUrl,
  type Measurement,
  type MeasurementParams,
} from "../api";

// --- URL sync helpers ---
function readUrlParams(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

function pushUrlParams(params: MeasurementParams) {
  const url = new URL(window.location.href);
  url.search = "";
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  window.history.replaceState({}, "", url.toString());
}

const headers = [
  { title: "Timestamp", key: "cpuTimestamp", sortable: true },
  { title: "Serial No.", key: "sensorSerNo", sortable: true },
  { title: "Rain Intensity (mm/h)", key: "rainIntensity", sortable: true },
  { title: "Rain Amt (mm)", key: "rainAmt", sortable: true },
  { title: "Wx Code (SYNOP)", key: "wxCode", sortable: true },
  { title: "Reflectivity (dBZ)", key: "radarReflectivity", sortable: true },
  { title: "Visibility (m)", key: "MORvisibility", sortable: true },
  { title: "Kinetic Energy (J/m\u00B2h)", key: "kineticEnergy", sortable: true },
  { title: "Housing Temp (\u00B0C)", key: "housingTemp", sortable: true },
  { title: "Laser Amp", key: "laserAmplitude", sortable: true },
  { title: "Particles", key: "particleCount", sortable: true },
  { title: "Status", key: "sensorStatusText", sortable: false },
];

const filterOps = [
  { title: "=", value: "eq" },
  { title: ">", value: "gt" },
  { title: ">=", value: "gte" },
  { title: "<", value: "lt" },
  { title: "<=", value: "lte" },
];

interface ColumnFilter {
  key: string;
  label: string;
  op: string;
  value: string;
}

const columnFilters = reactive<ColumnFilter[]>([
  { key: "rainIntensity", label: "Rain Intensity (mm/h)", op: "gte", value: "" },
  { key: "rainAmt", label: "Rain Amt (mm)", op: "gte", value: "" },
  { key: "wxCode", label: "Wx Code (SYNOP)", op: "eq", value: "" },
  { key: "housingTemp", label: "Housing Temp (\u00B0C)", op: "gte", value: "" },
  { key: "sensorStatus", label: "Status Code (0\u20133)", op: "eq", value: "" },
  { key: "particleCount", label: "Particles", op: "gte", value: "" },
]);

interface TimePreset {
  label: string;
  hours: number | null; // null = "All" (no time filter)
}

const timePresets: TimePreset[] = [
  { label: "1h", hours: 1 },
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "7d", hours: 24 * 7 },
  { label: "30d", hours: 24 * 30 },
  { label: "All", hours: null },
];

const drawer = ref(false);

const items = ref<Measurement[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const sortBy = ref<{ key: string; order: "asc" | "desc" }[]>([
  { key: "cpuTimestamp", order: "desc" },
]);
const loading = ref(false);
const error = ref("");

const startInput = ref("");
const endInput = ref("");
const activePreset = ref<string | null>(null);

function toIso(datetimeLocal: string): string {
  // datetime-local gives "YYYY-MM-DDTHH:MM", API expects full ISO
  return datetimeLocal ? datetimeLocal + ":00" : "";
}

function toDatetimeLocal(iso: string): string {
  // Trim seconds for the input value
  return iso ? iso.slice(0, 16) : "";
}

function applyPreset(preset: TimePreset) {
  if (preset.hours === null) {
    startInput.value = "";
    endInput.value = "";
  } else {
    const now = new Date();
    const start = new Date(now.getTime() - preset.hours * 3600_000);
    endInput.value = toDatetimeLocal(now.toISOString().slice(0, 19));
    startInput.value = toDatetimeLocal(start.toISOString().slice(0, 19));
  }
  page.value = 1;
  loadData();
}

function buildParams(): MeasurementParams {
  const sort =
    sortBy.value.length > 0
      ? (sortBy.value[0].order === "desc" ? "-" : "") + sortBy.value[0].key
      : "-cpuTimestamp";

  const startIso = toIso(startInput.value);
  const endIso = toIso(endInput.value);

  const params: MeasurementParams = {
    page: page.value,
    page_size: pageSize.value,
    sort,
    ...(startIso ? { start: startIso } : {}),
    ...(endIso ? { end: endIso } : {}),
  };

  for (const filter of columnFilters) {
    if (filter.value) {
      params[`${filter.key}__${filter.op}`] = filter.value;
    }
  }

  return params;
}

const csvUrl = computed(() => buildCsvUrl(buildParams()));

const activeFilterCount = computed(() => {
  let count = 0;
  if (startInput.value) count++;
  if (endInput.value) count++;
  for (const filter of columnFilters) {
    if (filter.value) count++;
  }
  return count;
});

async function loadData() {
  const params = buildParams();
  pushUrlParams(params);
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchMeasurements(params);
    items.value = data.items;
    total.value = data.total;
  } catch (e: any) {
    error.value = e.message;
    items.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function applyFilters() {
  page.value = 1;
  loadData();
}

function resetFilters() {
  startInput.value = "";
  endInput.value = "";
  activePreset.value = null;
  for (const filter of columnFilters) {
    filter.value = "";
    filter.op = filter.key === "wxCode" || filter.key === "sensorStatus" ? "eq" : "gte";
  }
  page.value = 1;
  sortBy.value = [{ key: "cpuTimestamp", order: "desc" }];
  loadData();
}

function onOptionsUpdate() {
  loadData();
}

function restoreFromUrl() {
  const q = readUrlParams();

  // Time filters
  if (q.has("start")) startInput.value = toDatetimeLocal(q.get("start")!);
  if (q.has("end")) endInput.value = toDatetimeLocal(q.get("end")!);

  // Pagination
  if (q.has("page")) page.value = Number(q.get("page"));
  if (q.has("page_size")) pageSize.value = Number(q.get("page_size"));

  // Sort
  const sortRaw = q.get("sort");
  if (sortRaw) {
    const desc = sortRaw.startsWith("-");
    const key = desc ? sortRaw.slice(1) : sortRaw;
    sortBy.value = [{ key, order: desc ? "desc" : "asc" }];
  }

  // Column filters
  for (const filter of columnFilters) {
    for (const op of ["eq", "gt", "gte", "lt", "lte"]) {
      const param = `${filter.key}__${op}`;
      if (q.has(param)) {
        filter.op = op;
        filter.value = q.get(param)!;
        break;
      }
    }
  }
}

onMounted(() => {
  restoreFromUrl();
  loadData();
});
</script>

<template>
  <v-container fluid>
    <!-- Toolbar -->
    <v-row class="mb-2" dense align="center">
      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-filter-variant"
          variant="tonal"
          @click="drawer = !drawer"
        >
          Filters
          <v-badge
            v-if="activeFilterCount > 0"
            :content="activeFilterCount"
            color="primary"
            inline
            class="ml-1"
          />
        </v-btn>
      </v-col>
      <v-col cols="auto">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-download"
          :href="csvUrl"
          target="_blank"
        >
          CSV
        </v-btn>
      </v-col>
      <v-spacer />
      <v-col cols="auto" class="text-medium-emphasis text-body-2">
        {{ total.toLocaleString() }} results
      </v-col>
    </v-row>

    <!-- Error alert -->
    <v-alert v-if="error" type="error" closable class="mb-4" @click:close="error = ''">
      {{ error }}
    </v-alert>

    <!-- Data table -->
    <v-data-table-server
      v-model:items-per-page="pageSize"
      v-model:page="page"
      v-model:sort-by="sortBy"
      :headers="headers"
      :items="items"
      :items-length="total"
      :loading="loading"
      hover
      density="compact"
      @update:options="onOptionsUpdate"
    />

    <!-- Filter drawer -->
    <v-navigation-drawer
      v-model="drawer"
      location="right"
      temporary
      width="340"
    >
      <v-toolbar density="compact" flat>
        <v-toolbar-title class="text-subtitle-1">Filters</v-toolbar-title>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="drawer = false" />
      </v-toolbar>

      <v-container class="pt-4">
        <!-- Time range section -->
        <div class="text-overline mb-2">Time Range</div>

        <v-btn-toggle
          v-model="activePreset"
          density="compact"
          variant="outlined"
          divided
          class="mb-3 flex-wrap"
        >
          <v-btn
            v-for="preset in timePresets"
            :key="preset.label"
            :value="preset.label"
            size="small"
            @click="applyPreset(preset)"
          >
            {{ preset.label }}
          </v-btn>
        </v-btn-toggle>

        <v-text-field
          v-model="startInput"
          label="Start"
          type="datetime-local"
          clearable
          density="compact"
          variant="outlined"
          hide-details
          class="mb-3"
        />
        <v-text-field
          v-model="endInput"
          label="End"
          type="datetime-local"
          clearable
          density="compact"
          variant="outlined"
          hide-details
          class="mb-5"
        />

        <!-- Column filters section -->
        <div class="text-overline mb-2">Column Filters</div>

        <div v-for="filter in columnFilters" :key="filter.key" class="mb-3">
          <v-text-field
            v-model="filter.value"
            :label="filter.label"
            clearable
            density="compact"
            variant="outlined"
            hide-details
          >
            <template #prepend-inner>
              <v-select
                v-model="filter.op"
                :items="filterOps"
                density="compact"
                variant="plain"
                hide-details
                class="op-select"
              />
            </template>
          </v-text-field>
        </div>

        <!-- Drawer actions -->
        <v-divider class="mb-4" />
        <v-btn color="primary" block class="mb-2" @click="applyFilters(); drawer = false">
          Apply
        </v-btn>
        <v-btn variant="outlined" block @click="resetFilters">
          Reset
        </v-btn>
      </v-container>
    </v-navigation-drawer>
  </v-container>
</template>

<style scoped>
.op-select {
  max-width: 56px;
  flex: 0 0 56px;
}
.op-select :deep(.v-field__input) {
  padding: 0;
  min-height: unset;
  font-size: 0.85rem;
}
</style>
