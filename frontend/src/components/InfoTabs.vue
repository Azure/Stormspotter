<template>
  <div class="q-pa-md" id="info-tabs">
    <div class="q-gutter-y-md">
      <q-card bordered>
        <q-tabs
          v-model="selectedTab"
          dense
          class="text-black"
          active-color="white"
          indicator-color="white"
          align="justify"
          narrow-indicator
          active-bg-color="accent"
        >
          <q-tab
            v-for="tab in tabs"
            :key="tab.name"
            :label="tab.name"
            :name="tab.name"
          />
        </q-tabs>

        <q-separator />

        <q-tab-panels v-model="selectedTab">
          <q-tab-panel v-for="tab in tabs" :key="tab.name" :name="tab.name">
            <component :is="tab.componentName"></component>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";
import DatabaseView from "./DatabaseView";
import InfoView from "./InfoView";
import QueryView from "./QueryView";

export default {
  name: "InfoTabs",
  computed: mapState(["currentElement"]),
  watch: {
    currentElement: async function (ele) {
      this.selectedTab = "Info";
    },
  },
  components: { DatabaseView, InfoView, QueryView },
  data() {
    return {
      selectedTab: "Database",
      tabs: [
        {
          name: "Database",
          componentName: "DatabaseView",
        },
        {
          name: "Info",
          componentName: "InfoView",
        },
        {
          name: "Queries",
          componentName: "QueryView",
        },
      ],
    };
  },
};
</script>

<style lang="sass">
.q-tabs
  background-color: black
  color: white !important

.q-tab-panel
  background-color: $grey-10
  color: white
  border-radius: 2px
</style>
