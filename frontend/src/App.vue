<template>
  <v-app>
    <v-app-bar title="Parsivel Dashboard" flat>
      <template #prepend>
        <v-icon icon="mdi-weather-rainy" />
      </template>
    </v-app-bar>

    <v-main>
      <MeasurementsTable />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import MeasurementsTable from "./components/MeasurementsTable.vue";
</script>
