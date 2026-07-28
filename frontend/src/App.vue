<script setup lang="ts">
import logoUrl from "./assets/logo.png";
import umtriLogo from "./assets/umtri-formal-white.png";
</script>

<template>
  <v-app>
    <!-- The title lives in the prepend slot, not the `title` prop, so the mark
         and the wordmark are one link back to the landing page. -->
    <v-app-bar flat class="brand-bar">
      <template #prepend>
        <!-- ml-3 (12px) + the toolbar's own 4px prepend margin = 16px, which is
             the side padding of the page v-container below. -->
        <router-link to="/" class="brand ml-3" aria-label="Go to the home page">
          <v-img :src="logoUrl" width="40" height="40" alt="" />
          <span class="brand-text">Parsivel Dashboard</span>
        </router-link>
      </template>

      <template #append>
        <!-- mr-3 (12px) + the toolbar's own 4px append margin = 16px, matching
             the inset on the left. A plain <img> rather than v-img: the logo is
             horizontal and its width follows its own aspect ratio. -->
        <img
          v-if="umtriLogo"
          :src="umtriLogo"
          alt="UMTRI"
          class="org-logo mr-3"
        />
        <div v-else class="org-logo org-logo--empty mr-3">UMTRI logo</div>
      </template>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: inherit;
  text-decoration: none;
  border-radius: 4px;
  padding-inline-end: 8px;
  transition: opacity 0.15s ease;
}
.brand:hover {
  opacity: 0.8;
}
.brand-text {
  font-size: 1.5rem;
  line-height: 2rem;
  white-space: nowrap;
}
.org-logo {
  height: 32px;
  width: auto;
  display: block;
}
/* Stand-in until the file arrives. The dashed edge marks it as unfinished. */
.org-logo--empty {
  display: flex;
  align-items: center;
  padding-inline: 12px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
