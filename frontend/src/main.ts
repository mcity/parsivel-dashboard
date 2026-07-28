import { createApp } from "vue";
import vuetify from "./plugins/vuetify";
// After the Vuetify import, so the app font override lands last.
import "./style.css";
import router from "./router";
import App from "./App.vue";

createApp(App).use(vuetify).use(router).mount("#app");
