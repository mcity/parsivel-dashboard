<script setup lang="ts">
// Ported from stunning-ui (MIT, @xiaoluoboding):
// github.com/xiaoluoboding/stunning-ui/blob/main/components/stunning/SpotlightCard.vue
// Changes: the pointer position comes from a local mousemove handler instead of
// VueUse (not a dependency here), and the surface uses Vuetify theme colours
// instead of Tailwind classes. The card draws its own surface so the glow can
// sit on the background and under the text.
import { ref } from "vue";

withDefaults(
  defineProps<{
    /** Colour of the glow at the pointer. */
    color?: string;
    /** Glow radius in pixels. */
    size?: number;
  }>(),
  { color: "rgba(var(--v-theme-primary), 0.16)", size: 300 },
);

const root = ref<HTMLElement | null>(null);

function onMove(event: MouseEvent) {
  const node = root.value;
  if (!node) return;
  const rect = node.getBoundingClientRect();
  node.style.setProperty("--spotlight-x", `${event.clientX - rect.left}px`);
  node.style.setProperty("--spotlight-y", `${event.clientY - rect.top}px`);
}
</script>

<template>
  <div
    ref="root"
    class="spotlight-card"
    :style="{ '--spotlight-size': `${size}px`, '--spotlight-color': color }"
    @mousemove="onMove"
  >
    <div class="spotlight-content"><slot /></div>
  </div>
</template>

<style scoped>
.spotlight-card {
  position: relative;
  height: 100%;
  overflow: hidden;
  /* Matches the 4px v-card default, so these sit level with the dashboard cards. */
  border-radius: 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.03);
  transition: border-color 0.25s ease;
}
.spotlight-card:hover {
  border-color: rgba(var(--v-theme-primary), 0.4);
}
.spotlight-card::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
  background: radial-gradient(
    var(--spotlight-size) circle at var(--spotlight-x) var(--spotlight-y),
    var(--spotlight-color),
    transparent 45%
  );
}
.spotlight-card:hover::before {
  opacity: 1;
}
.spotlight-content {
  position: relative;
  z-index: 1;
  height: 100%;
}

/* The glow follows the pointer, so it means nothing without one. */
@media (hover: none) {
  .spotlight-card::before {
    display: none;
  }
}
</style>
