<script setup lang="ts">
import { ref } from "vue";
import PhotoFrame from "./PhotoFrame.vue";

export interface Photo {
  /** Leave undefined until the real image exists; PhotoFrame draws a placeholder. */
  src?: string;
  alt: string;
  caption: string;
}

const props = defineProps<{
  items: Photo[];
  /** CSS aspect-ratio for every slide, so the frame never resizes between them. */
  ratio?: string;
}>();

const index = ref(0);

// Wraps at both ends, so neither arrow ever dead-ends.
function step(delta: number) {
  const count = props.items.length;
  if (count === 0) return;
  index.value = (index.value + delta + count) % count;
}
</script>

<template>
  <div class="photo-carousel">
    <!-- v-window, not v-carousel: v-carousel forces a fixed pixel height, while
         v-window sizes to the slide, so PhotoFrame keeps its aspect ratio.
         `continuous` makes a touch swipe wrap the same way the arrows do.
         The arrows live below the frame, not over it, so nothing covers the
         photo — hence no `show-arrows` here. -->
    <v-window v-model="index" continuous>
      <v-window-item v-for="(photo, i) in items" :key="i">
        <PhotoFrame :src="photo.src" :alt="photo.alt" :ratio="ratio" />
      </v-window-item>
    </v-window>

    <div class="d-flex align-center justify-space-between ga-4 mt-2">
      <p class="text-caption text-medium-emphasis mb-0">
        {{ items[index]?.caption }}
      </p>

      <div v-if="items.length > 1" class="controls">
        <v-btn
          icon="mdi-chevron-left"
          variant="text"
          density="comfortable"
          size="small"
          aria-label="Previous photo"
          @click="step(-1)"
        />

        <div class="dots" role="tablist">
          <button
            v-for="(photo, i) in items"
            :key="i"
            type="button"
            role="tab"
            class="dot"
            :class="{ 'dot--active': i === index }"
            :aria-selected="i === index"
            :aria-label="photo.alt"
            @click="index = i"
          />
        </div>

        <v-btn
          icon="mdi-chevron-right"
          variant="text"
          density="comfortable"
          size="small"
          aria-label="Next photo"
          @click="step(1)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: none;
}
.dots {
  display: flex;
  gap: 6px;
  padding-inline: 4px;
}
.dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  background: rgba(var(--v-theme-on-surface), 0.3);
  transition: background 0.2s ease;
}
.dot:hover {
  background: rgba(var(--v-theme-on-surface), 0.55);
}
.dot--active {
  background: rgb(var(--v-theme-primary));
}
</style>
