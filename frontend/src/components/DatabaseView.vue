<template>
  <div>
    <q-table
      :columns="statsColumns"
      :data="statsSummary"
      bordered
      dark
      card-class="bg-grey-9 text-white"
      dense
      hide-header
      hide-bottom
      separator="cell"
      title="Database Stats"
    />
    <q-separator vertical inset />
    <q-table
      :columns="nodeColumns"
      :data="currentNodeSummary"
      :pagination="pagination"
      :rows-per-page-options="[0]"
      bordered
      card-class="bg-black text-white"
      dense
      dark
      hide-pagination
      row-key="name"
      no-data-label="No Results"
      separator="cell"
      style="height: 400px;"
      table-class="text-white hide-scroll"
      table-header-class="text-white"
      title="Node Summary"
      virtual-scroll
    >
      <template v-slot:no-data>
        <div class="full-width row flex-center text-white q-gutter-sm">
          <span>
            No results
          </span>
          <q-btn
            :ripple="{ center: true }"
            color="secondary"
            label="Refresh"
            no-caps
            @click="dbSummary"
            :disabled="refreshing"
          />
        </div>
      </template>
    </q-table>
    <q-separator vertical inset />

    <div class="q-pa-none q-ma-none">
      <q-uploader
        @uploaded="finishUpload"
        auto-upload
        bordered
        color="deep-purple-10"
        dark
        field-name="upload"
        :headers="getNeo4jCreds"
        hide-upload-btn
        label="Stormcollector Upload"
        no-thumbnails
        ref="uploader"
        style="width: 100%;"
        url="http://localhost:9090/api/upload"
      >
      </q-uploader>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";

export default {
  name: "DatabaseView",
  computed: {
    ...mapState(["currentNodeSummary"]),
  },
  data() {
    return {
      refreshing: false,
      pagination: {
        sortBy: "name",
        rowsPerPage: 0,
      },
      nodeColumns: [
        {
          name: "name",
          required: true,
          label: "Node Type",
          align: "left",
          field: "name",
        },
        { name: "count", required: true, label: "Count", field: "count" },
      ],
      statsColumns: [
        {
          name: "name",
          required: true,
          label: "Name",
          align: "left",
          field: "name",
        },
        { name: "value", required: true, label: "Value", field: "value" },
      ],
      statsSummary: [],
    };
  },

  created() {
    this.dbSummary();
    this.timer = setInterval(this.dbSummary, 5000);
  },

  beforeDestroy() {
    clearInterval(this.timer);
  },

  methods: {
    dbSummary() {
      this.refreshing = true;
      this.$neo4j
        .run(
          "MATCH (n) RETURN count(labels(n)) AS count, labels(n) AS labels",
          {},
          {}
        )
        .then((res) => {
          let nodeSummary = [];
          res.records.forEach((record) => {
            let labels = record.get("labels");

            if (labels.length == 1) {
              nodeSummary.push({
                name: labels[0],
                count: record.get("count").toString(),
              });
            }

            if (labels.length > 1) {
              let primaryLabel = labels.filter(function (e) {
                return !(e == "AADObject" || e == "AzureResource");
              });
              nodeSummary.push({
                name: primaryLabel[0],
                count: record.get("count").toString(),
              });
            }
          });
          this.$store.dispatch("currentNodeSummary", nodeSummary);
        });

      this.statsSummary = [];
      let db = `${this.$store.getters.ssneo4j_scheme}://${this.$store.getters.ssneo4j_host}:${this.$store.getters.ssneo4j_port}`;
      this.statsSummary.push({ name: "Database", value: db });
      this.statsSummary.push({
        name: "User",
        value: this.$store.getters.ssneo4j_user,
      });
      this.refreshing = false;
    },
    getNeo4jCreds() {
      return [
        { name: "X-Neo4j-User", value: this.$store.getters.ssneo4j_user },
        { name: "X-Neo4j-Pass", value: this.$store.getters.ssneo4j_pass },
      ];
    },
    finishUpload() {
      this.$refs.uploader.reset();
    },
  },
};
</script>
