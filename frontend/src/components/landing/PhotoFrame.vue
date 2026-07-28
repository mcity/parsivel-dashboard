<script setup lang="ts">
// Shows a photo, or a labelled placeholder while the photo is missing.
// The landing page needs real hardware images that aren't in the repo yet, and
// a missing import breaks the build — so the image stays optional here.
withDefaults(
  defineProps<{
    src?: string;
    alt?: string;
    caption?: string;
    /** CSS aspect-ratio for the frame, e.g. "4 / 3". */
    ratio?: string;
  }>(),
  { ratio: "4 / 3" },
);
</script>

<template>
  <figure class="photo-frame ma-0">
    <div class="frame" :style="{ aspectRatio: ratio }">
      <v-img v-if="src" :src="src" :alt="alt" cover class="fill-height" />
      <div v-else class="placeholder">
        <v-icon icon="mdi-image-outline" size="48" class="mb-2" />
        <span class="text-body-2">{{ alt || "Photo" }}</span>
      </div>
    </div>
    <figcaption v-if="caption" class="text-caption text-medium-emphasis mt-2">
      {{ caption }}
    </figcaption>
  </figure>
</template>

<style scoped>
.frame {
  width: 100%;
  overflow: hidden;
  /* Matches the 4px v-card default, so these sit level with the dashboard cards. */
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* Dashed edge marks this as a stand-in, not a broken image. */
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.22);
  border-radius: 4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
