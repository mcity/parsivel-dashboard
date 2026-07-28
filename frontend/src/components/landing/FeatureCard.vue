<script setup lang="ts">
import SpotlightCard from "../stunning/SpotlightCard.vue";

defineProps<{
  icon: string;
  title: string;
  text: string;
}>();
</script>

<template>
  <SpotlightCard class="feature-card">
    <div class="pa-5">
      <v-icon :icon="icon" size="28" color="primary" class="mb-3" />
      <div class="text-subtitle-1 font-weight-medium mb-1">{{ title }}</div>
      <div class="text-body-2 text-medium-emphasis">{{ text }}</div>
    </div>
  </SpotlightCard>
</template>

<style scoped>
.feature-card {
  transition: transform 0.15s ease;
}
.feature-card:hover {
  transform: translateY(-2px);
}
</style>
