import Store from "../store/index.js";

const routes = [
  {
    path: "/dashboard",
    component: () => import("layouts/MainLayout.vue"),
  },
  {
    path: "/",
    name: "Login",
    component: () => import("pages/Login.vue"),
  },

  // Always leave this as last one,
  // but you can also remove it
  {
    path: "*",
    component: () => import("pages/Error404.vue"),
  },
];

export default routes;
