<template>
  <v-app>
    <v-app-bar title="Parsivel Dashboard" flat>
      <template #prepend>
        <v-icon icon="mdi-weather-rainy" />
      </template>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>
