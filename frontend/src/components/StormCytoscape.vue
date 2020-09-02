<template>
  <cytoscape
    :afterCreated="afterCreated"
    :config="config()"
    :preConfig="preConfig"
    ref="cy"
    v-on:click="clearSelected"
  >
    <cy-element
      v-for="def in cyElements"
      :key="`${def.data.id}`"
      :definition="def"
      v-on:click="showData($event, def)"
    />
  </cytoscape>
</template>

<script>
import VueCytoscape from "vue-cytoscape";
import config from "../cy-config";
import { mapState } from "vuex";
import cxtmenu from "cytoscape-cxtmenu";
import coseBilkent from "cytoscape-cose-bilkent";
import dagre from "cytoscape-dagre";
import cola from "cytoscape-cola";
import klay from "cytoscape-klay";
import { isNode, isRelationship } from "neo4j-driver/lib/graph-types.js";

let resolveCy = null;
export const cyPromise = new Promise((resolve) => (resolveCy = resolve));

export default {
  name: "StormCytoscape",
  data() {
    return {
      currentElement: null,
      existingCytoscape: false,
    };
  },
  created() {
    let payload = { query: "MATCH (n) RETURN n LIMIT 25", expand: false };
    this.$store.dispatch("makeQueryElements", payload);
  },
  computed: mapState(["layoutMode", "cyElements"]),
  watch: {
    cyElements: async function (val) {
      const cy = await cyPromise;
      if (val.length) {
        this.$nextTick(() => {
          cy.layout(this.layoutMode).run();
          cy.center();
          cy.fit(null, 200);
          cy.maxZoom(2);
        });
      }
    },
    layoutMode: async function (val) {
      const cy = await cyPromise;
      cy.layout(val).run();
      cy.center();

      cy.fit(null, 200);
      cy.maxZoom(2);
    },
  },
  methods: {
    preConfig(cytoscape) {
      cytoscape.use(coseBilkent);
      cytoscape.use(klay);
      cytoscape.use(cola);
      cytoscape.use(dagre);
      if (!cytoscape("core", "cxtmenu")) {
        cytoscape.use(cxtmenu);
      }
    },
    config() {
      const noElementsConfig = { ...config };
      noElementsConfig.layout = this.$store.getters.layoutMode;
      return noElementsConfig;
    },
    async afterCreated(cy) {
      const store = this.$store;
      let defaults = {
        menuRadius: 100, // the radius of the circular menu in pixels
        selector: "node", // elements matching this Cytoscape.js selector will trigger cxtmenus
        commands: [
          // an array of commands to list in the menu or a function that returns the array

          {
            content: "Expand All",
            select: function (ele) {
              let payload = {
                query: `MATCH (a)-[r]-(t) WHERE id(a) = ${
                  ele.id().split("_")[1]
                } RETURN *`,
                expand: true,
              };

              store.dispatch("makeQueryElements", payload);
            },
            enabled: true,
          },

          {
            content: "Expand Outgoing",
            select: function (ele) {
              let payload = {
                query: `MATCH (a)-[r]->(t) WHERE id(a) = ${
                  ele.id().split("_")[1]
                } RETURN *`,
                expand: true,
              };
              store.dispatch("makeQueryElements", payload);
            },
            enabled: true,
          },
          {
            content: "Expand Incoming",
            select: function (ele) {
              let payload = {
                query: `MATCH (a)<-[r]-(t) WHERE id(a) = ${
                  ele.id().split("_")[1]
                } RETURN *`,
                expand: true,
              };

              store.dispatch("makeQueryElements", payload);
            },
            enabled: true,
          },
          {
            content: "Filter to this Node",
            select: function (ele) {
              let payload = {
                query: `MATCH (a) WHERE id(a) = ${
                  ele.id().split("_")[1]
                } RETURN a`,
                expand: false,
              };
              store.dispatch("makeQueryElements", payload);
            },

            enabled: true,
          },
          // {
          //   content: "Filter to this Path",
          //   contentStyle: {},
          //   select: function (ele) {
          //     let payload = {
          //       query: `MATCH (a)-[r]-(t) WHERE id(a) = ${
          //         ele.id().split("_")[1]
          //       } RETURN *`,
          //       expand: false,
          //     };
          //     store.dispatch("makeQueryElements", payload);
          //   },

          //   enabled: true,
          // },
        ], // function( ele ){ return [ /*...*/ ] }, // a function that returns commands or a promise of commands
        fillColor: "rgba(0, 13, 69, 0.75)", // the background colour of the menu
        activeFillColor: "rgba(194, 74, 0, 0.75)", // the colour used to indicate the selected command
        activePadding: 20, // additional size in pixels for the active command
        indicatorSize: 24, // the size in pixels of the pointer to the active command
        separatorWidth: 3, // the empty spacing in pixels between successive commands
        spotlightPadding: 16, // extra spacing in pixels between the element and the spotlight
        minSpotlightRadius: 20, // the minimum radius in pixels of the spotlight
        maxSpotlightRadius: 20, // the maximum radius in pixels of the spotlight
        openMenuEvents: "cxttapstart taphold", // space-separated cytoscape events that will open the menu; only `cxttapstart` and/or `taphold` work here
        itemColor: "white", // the colour of text in the command's content
        itemTextShadowColor: "transparent", // the text shadow colour of the command's content
        zIndex: 2, // the z-index of the ui div
        atMouse: false, // draw menu at mouse position
      };

      resolveCy(cy);
      cy.cxtmenu(defaults);
    },
    async clearSelected(event) {
      if (
        event.target.constructor.name === "Core" ||
        //Event changes to "Qa" in prod for whatever reason. Don't remove.
        event.target.constructor.name === "Qa"
      ) {
        const cy = await cyPromise;
        cy.nodes().classes([]);
        cy.edges().classes([]);
      }
    },
    async showData(event, obj) {
      const cy = await cyPromise;
      console.log(cy.zoom());
      this.$store.dispatch("currentElement", obj).then(() => {
        var unSelectedNodes = cy.nodes(":unselected");
        var selectedNodes = cy.nodes(":selected");
        var unSelectedEdges = cy.edges(":unselected");
        var selectedEdges = cy.edges(":selected");

        unSelectedNodes
          .outgoers()
          .toggleClass("outgoingNode outgoingEdge", false);
        unSelectedNodes
          .incomers()
          .toggleClass("incomingNode incomingEdge", false);

        unSelectedNodes.toggleClass("opacityDim", true);
        unSelectedNodes.outgoers().toggleClass("opacityDim", true);
        unSelectedNodes.incomers().toggleClass("opacityDim", true);

        unSelectedEdges.toggleClass("opacityDim", true);
        unSelectedEdges.targets().toggleClass("opacityDim", true);
        unSelectedEdges.sources().toggleClass("opacityDim", true);

        if (isNode(obj)) {
          selectedNodes.outgoers().toggleClass("opacityDim", false);
          selectedNodes.incomers().toggleClass("opacityDim", false);
          selectedNodes.toggleClass("opacityDim", false);

          selectedNodes
            .outgoers()
            .toggleClass("outgoingNode outgoingEdge", true);
          selectedNodes
            .incomers()
            .toggleClass("incomingNode incomingEdge", true);
        } else if (isRelationship(obj)) {
          selectedEdges
            .targets()
            .toggleClass("outgoingNode outgoingEdge", true);
          selectedEdges.toggleClass("outgoingNode outgoingEdge", true);
          selectedEdges
            .sources()
            .toggleClass("incomingNode incomingEdge", true);

          selectedEdges.targets().toggleClass("opacityDim", false);
          selectedEdges.sources().toggleClass("opacityDim", false);
          selectedEdges.toggleClass("opacityDim", false);
        }
      });
    },
  },
};
</script>
