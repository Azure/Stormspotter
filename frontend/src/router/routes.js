import Store from "../store/index.js";

const routes = [
  {
    path: "/dashboard",
    component: () => import("layouts/MainLayout.vue"),
  },
  {
    path: "/",
    name: "Login",
    alias: "/login",
    component: () => import("pages/Login.vue"),
  },
];

export default routes;
