<script setup lang="ts">
// Ported from stunning-ui (MIT, @xiaoluoboding):
// github.com/xiaoluoboding/stunning-ui/blob/main/components/stunning/DotPattern.vue
// Changes: Tailwind utility classes became scoped CSS (this app has no
// Tailwind), the dot colour follows the Vuetify theme, and the pattern id comes
// from Vue's useId() instead of the repo's ~/lib/utils helper.
import { useId } from "vue";

withDefaults(
  defineProps<{
    width?: number;
    height?: number;
    x?: number;
    y?: number;
    cx?: number;
    cy?: number;
    /** Dot radius. */
    cr?: number;
  }>(),
  { width: 16, height: 16, x: 0, y: 0, cx: 1, cy: 1, cr: 1 },
);

// Each instance needs its own id, or a second instance would point at the
// first one's <pattern>.
const id = `dot-pattern-${useId()}`;
</script>

<template>
  <svg aria-hidden="true" class="dot-pattern">
    <defs>
      <pattern
        :id="id"
        :width="width"
        :height="height"
        patternUnits="userSpaceOnUse"
        patternContentUnits="userSpaceOnUse"
        :x="x"
        :y="y"
      >
        <circle :cx="cx" :cy="cy" :r="cr" />
      </pattern>
    </defs>
    <rect width="100%" height="100%" stroke-width="0" :fill="`url(#${id})`" />
  </svg>
</template>

<style scoped>
.dot-pattern {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  fill: rgba(var(--v-theme-on-surface), 0.16);
}
</style>
