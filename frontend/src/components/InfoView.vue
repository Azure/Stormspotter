<template>
  <div>
    <div class="row q-pa-none q-ma-none">
      <q-toggle
        v-model="rawData"
        class="col-md-5"
        color="red"
        keep-color
        readonly
        label="Raw Data"
      />
    </div>
    <q-separator vertical inset />

    <div class="row q-pa-none q-ma-none">
      <codemirror
        v-if="rawData"
        ref="cmRaw"
        v-model="eleRawData"
        :options="cmOptions"
        style="width: 100%;"
      ></codemirror>
      <!-- <q-input
        v-if="rawData"
        v-model="eleRawData"
        style="width: 400px;"
        filled
        autogrow
      /> -->
      <q-table
        :columns="infoColumns"
        :data="eleData"
        :pagination="pagination"
        :rows-per-page-options="[0]"
        :filter="infoFilter"
        bordered
        card-class="bg-black text-white"
        dark
        dense
        hide-bottom
        hide-pagination
        no-data-label="No Results"
        row-key="property"
        separator="cell"
        style="max-height: 800px; width: 100%;"
        table-class="text-white hide-scroll"
        table-header-class="text-white text-h4"
        v-else
        virtual-scroll
      >
        <template v-slot:top-left>
          <q-input
            dense
            debounce="300"
            v-model="infoFilter"
            placeholder="Search"
          >
            <template v-slot:prepend>
              <q-icon name="search" color="white" />
            </template>
          </q-input>
        </template>
      </q-table>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";
import { codemirror } from "vue-codemirror";
import { join } from "lodash";
import "codemirror/lib/codemirror.css";
import "codemirror/mode/javascript/javascript.js";
import "codemirror/theme/ayu-dark.css";
import "codemirror/addon/display/autorefresh";
import "codemirror/addon/scroll/simplescrollbars.js";
import "codemirror/addon/scroll/simplescrollbars.css";

export default {
  name: "InfoView",
  components: { codemirror },
  computed: mapState(["currentElement"]),
  watch: {
    currentElement: async function (ele) {
      this.updateInfo(ele);
    },
  },
  created() {
    let curEle = this.$store.getters.currentElement;
    if (curEle !== undefined) {
      this.updateInfo(curEle);
    }
  },
  data() {
    return {
      infoFilter: "",
      pagination: {
        sortBy: "property",
        rowsPerPage: 0,
      },
      cmOptions: {
        mode: {
          name: "javascript",
          json: true,
          statementIndex: 4,
        },
        theme: "ayu-dark",
        scrollbarStyle: "overlay",
        readOnly: true,
        lineNumbers: true,
        lineWrapping: true,
        tabSize: 4,
      },
      rawData: false,
      eleData: [],
      eleRawData: [],
      infoColumns: [
        {
          name: "property",
          required: true,
          label: "Property",
          align: "left",
          field: "property",
          sortable: true,
          filter: true,
          style: "min-width: 220px;overflow-wrap: anywhere;",
        },
        {
          name: "value",
          align: "left",
          required: true,
          label: "Value",
          field: "value",
          sortable: true,
          style: "overflow-wrap: anywhere;background-color: #141414;",
        },
      ],
    };
  },

  methods: {
    updateInfo(ele) {
      let infoSummary = [];
      let hasRaw = false;
      for (var [key, value] of Object.entries(ele.properties)) {
        let finalValue = "";

        if (key === "raw") {
          this.eleRawData = value;
          hasRaw = true;
          continue;
        }

        if (value === "None") {
          continue;
        } else if (Array.isArray(value)) {
          // TODO: Figure out proper display for showing lists
          finalValue = join(value, "\n");
        } else {
          finalValue = value.toString();
        }

        infoSummary.push({
          property: key,
          value: finalValue,
        });
      }
      this.eleData = infoSummary;
      if (!hasRaw) {
        this.eleRawData = [];
      }
    },
  },
};
</script>
