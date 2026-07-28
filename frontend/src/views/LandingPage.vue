<script setup lang="ts">
import PhotoCarousel, { type Photo } from "../components/landing/PhotoCarousel.vue";
import FeatureCard from "../components/landing/FeatureCard.vue";

// --- Photos -------------------------------------------------------------
// Slides for the hero carousel.
import sensorPhoto from "../assets/sensor.jpg";
import locationPhoto from "../assets/google_earth_view.png";

const photos: Photo[] = [
  {
    src: sensorPhoto,
    alt: "OTT Parsivel² sensor",
    caption: "The sensor in its field installation.",
  },
  {
    src: locationPhoto,
    alt: "Satellite view of the sensor location",
    caption: "The sensor is at 42.298240,-83.703309, 277.3 meters above mean sea level.",
  },
];

// --- External references ------------------------------------------------
const HARDWARE_URL = "https://www.ott.com/products/parsivel";
const MANUAL_URL =
  "https://cdn.hach.com/1XMCM0ZF/at/br9qp8bxsk8bn6nzxjxxq3pf/BA_Parsivel2_EN_70210002BE.pdf";

const features = [
  {
    icon: "mdi-weather-pouring",
    title: "Rain rate and totals",
    text: "Intensity in mm/h plus a running accumulation.",
  },
  {
    icon: "mdi-chart-scatter-plot",
    title: "Drop size and speed",
    text: "Every particle is sorted into one of 32 diameter classes and 32 fall-speed classes.",
  },
  {
    icon: "mdi-weather-snowy-rainy",
    title: "Precipitation type",
    text: "A SYNOP present-weather code separates drizzle, rain, snow, and hail.",
  },
  {
    icon: "mdi-radar",
    title: "Reflectivity and visibility",
    text: "Equivalent radar reflectivity in dBZ, and visibility through the precipitation in meters.",
  },
];
</script>

<template>
  <div class="landing">
    <!-- Hero -->
    <section class="hero">
      <v-container class="hero-body py-12">
        <v-row align="center" class="mb-4">
          <v-col cols="12" md="6">
            <div class="text-overline text-primary mb-2">
              OTT Parsivel² &middot; laser disdrometer
            </div>
            <h1 class="text-h3 font-weight-medium mb-4">
              UMTRI precipitation measurement archive
            </h1>
            <p class="text-body-1 text-medium-emphasis mb-4">
              This dashboard reads and visualizes the measurement archive of an OTT Parsivel²
              laser disdrometer located outside the University of Michigan Transportation Research Institute (UMTRI) building. 
            </p>
            <p class="text-body-1 text-medium-emphasis mb-4">
              The sensor projects a flat laser sheet and measures every particle that falls through it. 
              From the size and the speed of those particles it derives rain rate, accumulated
              rain, precipitation type, radar reflectivity, visibility, and
              kinetic energy. This data is then recorded at one minute intervals.
            </p>
            <v-btn
              color="primary"
              size="large"
              append-icon="mdi-arrow-right"
              to="/dashboard"
            >
              See the data
            </v-btn>
          </v-col>

          <v-col cols="12" md="6">
            <PhotoCarousel :items="photos" />
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- What the sensor records -->
    <v-container class="py-8">
      <h2 class="text-h5 font-weight-medium mb-6">What the sensor records</h2>
      <v-row>
        <v-col v-for="f in features" :key="f.title" cols="12" sm="6" md="3">
          <FeatureCard :icon="f.icon" :title="f.title" :text="f.text" />
        </v-col>
      </v-row>
    </v-container>

    <!-- Hardware and documentation. Last section on the page, so it carries the
         bottom padding. -->
    <v-container class="py-8 pb-16">
      <h2 class="text-h5 font-weight-medium mb-6">The hardware</h2>
      <v-row>
        <v-col cols="12" md="6">
          <v-card variant="outlined" class="fill-height">
            <v-card-item>
              <div class="text-subtitle-1 font-weight-medium mb-1">
                OTT Parsivel² laser weather sensor
              </div>
              <div class="text-body-2 text-medium-emphasis">
                The manufacturer product page: specifications, measuring
                principle, and ordering information.
              </div>
            </v-card-item>
            <v-card-actions>
              <v-btn
                variant="text"
                color="primary"
                append-icon="mdi-open-in-new"
                :href="HARDWARE_URL"
                target="_blank"
                rel="noopener"
              >
                Visit ott.com
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="fill-height">
            <v-card-item>
              <div class="text-subtitle-1 font-weight-medium mb-1">
                Operating instructions (PDF)
              </div>
              <div class="text-body-2 text-medium-emphasis">
                The full manual, part 70.210.002.BE. It defines the telegram
                fields, the SYNOP weather codes, the 32 class midpoints this
                dashboard decodes, and more. 
              </div>
            </v-card-item>
            <v-card-actions>
              <v-btn
                variant="text"
                color="primary"
                append-icon="mdi-file-pdf-box"
                :href="MANUAL_URL"
                target="_blank"
                rel="noopener"
              >
                Open the manual
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<style scoped>
.landing h1 {
  line-height: 1.2;
}
.hero {
  position: relative;
  overflow: hidden;
}
/* One wash of the theme's primary colour, anchored at the top and fading out
   before the section ends. It gives the hero depth with no repeating shape,
   and it follows the theme because the colour comes from a Vuetify variable. */
.hero::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(
    120% 90% at 50% 0%,
    rgba(var(--v-theme-primary), 0.15),
    transparent 60%
  );
}
/* Positioned, so the content paints above the wash. */
.hero-body {
  position: relative;
}
</style>
