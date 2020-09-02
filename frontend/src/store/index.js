import Vue from "vue";
import Vuex from "vuex";

// import example from './module-example'
import VueCytoscape from "vue-cytoscape";
import VueNeo4j from "vue-neo4j";
import { uniqBy, filter } from "lodash";
import { isNode, isRelationship } from "neo4j-driver/lib/graph-types.js";

Vue.use(VueCytoscape);
Vue.use(VueNeo4j);
Vue.use(Vuex);

/*
 * If not building with SSR mode, you can
 * directly export the Store instantiation;
 *
 * The function below can be async too; either use
 * async/await or return a Promise which resolves
 * with the Store instance.
 */

export default function (/* { ssrContext } */) {
  const Store = new Vuex.Store({
    state: {
      ssneo4j_user: window.localStorage.getItem("ssneo4j_user"),
      ssneo4j_pass: window.localStorage.getItem("ssneo4j_pass"),
      ssneo4j_host: window.localStorage.getItem("ssneo4j_host"),
      ssneo4j_port: window.localStorage.getItem("ssneo4j_port"),
      ssneo4j_scheme: window.localStorage.getItem("ssneo4j_scheme"),
      ss_remember: window.localStorage.getItem("ss_remember"),
      isLoggedIn: false,
      layoutMode: {},
      cyElements: [],
      currentElement: undefined,
      currentNodeSummary: [],
    },

    mutations: {
      auth_success: (state, payload) => {
        state.isLoggedIn = true;
        state.ssneo4j_user = payload.user;
        state.ssneo4j_pass = payload.pass;
        state.ssneo4j_scheme = payload.scheme;
        state.ssneo4j_host = payload.host;
        state.ssneo4j_port = payload.port;
        if (payload.remember) {
          window.localStorage.setItem("ssneo4j_user", payload.user);
          window.localStorage.setItem("ssneo4j_pass", payload.pass);
          window.localStorage.setItem("ssneo4j_host", payload.host);
          window.localStorage.setItem("ssneo4j_port", payload.port);
          window.localStorage.setItem("ssneo4j_scheme", payload.scheme);
          window.localStorage.setItem("ss_remember", "true");
        } else {
          window.localStorage.setItem("ss_remember", "false");
        }
      },
      goLogout: (state) => {
        window.localStorage.removeItem("ssneo4j_user");
        window.localStorage.removeItem("ssneo4j_pass");
        window.localStorage.removeItem("ssneo4j_host");
        window.localStorage.removeItem("ssneo4j_port");
        window.localStorage.removeItem("ssneo4j_scheme");
        window.localStorage.removeItem("ss_remember");
        state.isLoggedIn = false;
        state.cyElements = [];
        state.currentElement = undefined;
        state.currentNodeSummary = [];
      },
      changeMode(state, newState) {
        state.layoutMode = newState;
      },
      updateElements(state, newEles) {
        state.cyElements = newEles;
      },
      updateNodeSummary(state, stats) {
        state.currentNodeSummary = stats;
      },
      setLoggedIn(state, value) {
        state.isLoggedIn = value;
      },
      setCurrentElement(state, curEle) {
        state.currentElement = curEle;
      },
    },

    getters: {
      ssneo4j_user: (state) => {
        return state.ssneo4j_user;
      },
      ssneo4j_pass: (state) => {
        return state.ssneo4j_pass;
      },
      isLoggedIn: (state) => {
        return state.isLoggedIn;
      },
      ssneo4j_port: (state) => {
        return state.ssneo4j_port;
      },
      ssneo4j_host: (state) => {
        return state.ssneo4j_host;
      },
      ssneo4j_scheme: (state) => {
        return state.ssneo4j_scheme;
      },
      layoutMode: (state) => {
        return state.layoutMode;
      },
      cyElements: (state) => {
        return state.cyNodes;
      },
      currentElement: (state) => {
        return state.currentElement;
      },
      currentNodeSummary: (state) => {
        return state.currentNodeSummary;
      },
    },

    actions: {
      setAuth({ commit }, payload) {
        commit("auth_success", payload);
      },
      loggedIn({ commit }) {
        commit("setLoggedIn", true);
      },
      logout({ commit }) {
        commit("goLogout");
      },
      currentElement({ commit }, payload) {
        commit("setCurrentElement", payload);
      },
      currentNodeSummary({ commit }, payload) {
        commit("updateNodeSummary", payload);
      },

      makeQueryElements({ commit, state }, payload) {
        Vue.prototype.$neo4j
          .run(payload.query, {}, {})
          .then((res) => {
            let resNodes = [];
            let resEdges = [];
            let records = res["records"];

            if (records.length === 0) {
              Vue.prototype.$q.notify({
                color: "red",
                message: "No results found",
                timeout: 3000,
              });
            } else {
              records.forEach((record) => {
                for (const [key, value] of Object.entries(record.keys)) {
                  let obj = record.get(value);
                  obj.data = {};
                  obj.classes = "";

                  if (isNode(obj)) {
                    if (obj["properties"]["name"].charAt(0) === "/") {
                      obj.data.name = obj["properties"]["name"]
                        .split("/")
                        .pop();
                    } else {
                      obj.data.name = obj["properties"]["name"];
                    }
                    obj.data.type = obj["properties"]["type"];

                    obj.group = "nodes";
                    obj.data.id = "node_" + obj["identity"].toString();
                    resNodes.push(obj);
                  } else if (isRelationship(obj)) {
                    obj.data.source = "node_" + obj["start"].toString();
                    obj.data.target = "node_" + obj["end"].toString();
                    obj.data.id = "edge_" + obj["identity"].toString();
                    obj.data.type = obj.type;
                    obj.group = "edges";

                    resEdges.push(obj);
                  } else {
                    console.log(
                      "If you see this, something's wrong. Not a Node or Relationship",
                      obj
                    );
                  }
                }
              });

              if (payload.expand) {
                let curNodes = filter(state.cyElements, ["group", "nodes"]);
                let uniqNodes = uniqBy([...resNodes, ...curNodes], "data.id");

                let curEdges = filter(state.cyElements, ["group", "edges"]);
                let uniqEdges = uniqBy([...resEdges, ...curEdges], "data.id");

                commit("updateElements", [...uniqNodes, ...uniqEdges]);
              } else {
                let uniqNodes = uniqBy(resNodes, "data.id");
                let uniqEdges = uniqBy(resEdges, "data.id");
                commit("updateElements", [...uniqNodes, ...uniqEdges]);
              }
            }
          })
          .catch((err) => {
            Vue.prototype.$q.notify({
              color: "red",
              message: err.message,
              timeout: 3000,
            });
          });
      },
    },

    // enable strict mode (adds overhead!)
    // for dev mode only
    strict: process.env.DEV,
  });

  return Store;
}
