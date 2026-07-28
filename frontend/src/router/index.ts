import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import LandingPage from "../views/LandingPage.vue";
import MeasurementsTable from "../components/MeasurementsTable.vue";
import NotFound from "../views/NotFound.vue";

const routes: RouteRecordRaw[] = [
  { path: "/", name: "landing", component: LandingPage },
  { path: "/dashboard", name: "dashboard", component: MeasurementsTable },
  // Catch-all: any path that doesn't match a route above renders the 404 page
  // instead of silently falling back to the landing page.
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound },
];

export default createRouter({
  history: createWebHistory(),
  routes,
  // The dashboard writes its filter state into the query string, so only scroll
  // to the top on a real page change, not on a filter edit.
  scrollBehavior: (to, from) => (to.path === from.path ? false : { top: 0 }),
});
