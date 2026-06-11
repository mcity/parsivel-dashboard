import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import MeasurementsTable from "../components/MeasurementsTable.vue";
import NotFound from "../views/NotFound.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", name: "dashboard", component: MeasurementsTable },
  // Catch-all: any path that doesn't match a route above renders the 404 page
  // instead of silently falling back to the dashboard.
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
