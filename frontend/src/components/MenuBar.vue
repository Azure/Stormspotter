<template>
  <div>
    <q-list id="menu-bar">
      <q-item class="shadow-10">
        <q-item-section>
          <q-btn
            flat
            push
            outline
            dense
            size="lg"
            padding="none none"
            color="white"
            icon="insert_chart"
            @click="changeMode"
          >
            <q-tooltip
              transition-show="fade"
              transition-hide="fade"
              self="center left"
              anchor="center right"
              content-class="tooltip"
              class="bg-indigo-10"
              >Change Graph Layout <br />
              Current: {{ layoutMode.name }}
            </q-tooltip>
          </q-btn>
        </q-item-section>
      </q-item>
      <q-item class="shadow-10 q-ma-none">
        <q-item-section>
          <q-btn
            flat
            push
            outline
            dense
            size="lg"
            padding="none none"
            color="white"
            icon="logout"
            @click="logout"
          >
            <q-tooltip
              transition-show="fade"
              transition-hide="fade"
              self="center left"
              anchor="center right"
              content-class="tooltip"
              class="bg-indigo-10"
              >Logout <br />
            </q-tooltip>
          </q-btn>
        </q-item-section>
      </q-item>
    </q-list>
  </div>
</template>

<script>
import { mapState } from "vuex";

export default {
  name: "MenuBar",
  computed: mapState(["layoutMode"]),
  data() {
    return {
      curMode: 0,
      modes: [
        {
          name: "klay",
          nodeDimensionsIncludeLabels: true,
          fit: true,
          animate: true,
          klay: {
            compactComponents: true,
            direction: "RIGHT",
            edgeRouting: "POLYLINE",
            layoutHierarchy: false,
            thoroughness: 100,
            edgeSpacingFactor: 2,
            nodeLayering: "LONGEST_PATH",
            nodePlacement: "LINEAR_SEGMENTS",
          },
        },
        {
          name: "cose-bilkent",
          nodeDimensionsIncludeLabels: true,
          fit: true,
          animate: true,
          idealEdgeLength: 75,
          randomize: true,
          nodeRepulsion: 5000,
          numIter: 5000,
        },
        {
          name: "dagre",
          nodeDimensionsIncludeLabels: true,
          animate: true,
          fit: true,
        },
      ],
    };
  },
  created() {
    this.$store.commit("changeMode", this.modes[0]);
  },
  methods: {
    changeMode() {
      this.curMode++;
      if (this.curMode === this.modes.length) {
        this.$store.commit("changeMode", this.modes[0]);
        this.curMode = 0;
      } else {
        this.$store.commit("changeMode", this.modes[this.curMode]);
      }
    },
    logout() {
      this.$q
        .dialog({
          dark: true,
          title: "Confirm",
          message: "Are you sure you want to log out?",
          cancel: true,
          persistent: true,
        })
        .onOk(() => {
          this.$store.dispatch("logout").then(() => {
            this.$router.push("/");
          });
        });
    },
  },
};
</script>

<style lang="sass">
.tooltip
  font-size: 14px
</style>
