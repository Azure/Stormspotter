<template>
  <div class="q-pa-md">
    <q-list padding class="q-pa-sm rounded-borders">
      <q-expansion-item
        class="exp-item"
        dense
        dense-toggle
        label="Raw Query"
        :duration="100"
      >
        <q-form
          @submit="submitQuery"
          ref="queryForm"
          autocorrect="off"
          autocapitalize="off"
          autocomplete="off"
          spellcheck="false"
        >
          <codemirror
            ref="cm"
            name="query"
            v-model="code"
            :options="cmOptions"
            style="width: 400px;"
          ></codemirror>
          <q-btn
            size="lg"
            color="$accent"
            class="full-width text-white"
            label="Submit Query"
            type="submit"
          />
        </q-form>
      </q-expansion-item>
    </q-list>
  </div>
</template>

<script>
import { codemirror } from "vue-codemirror";
import "codemirror/mode/cypher/cypher.js";
import "codemirror/lib/codemirror.css";
import "codemirror/theme/neo.css";
import "codemirror/addon/display/autorefresh";
import "codemirror/addon/scroll/simplescrollbars.js";
import "codemirror/addon/scroll/simplescrollbars.css";
import { Notify } from "quasar";

export default {
  components: { codemirror },
  name: "DropdownQuery",
  data() {
    return {
      search: "",
      code: "",
      cmOptions: {
        mode: "application/x-cypher-query",
        lineNumbers: true,
        autofocus: true,
        theme: "neo",
        lint: true,
        lineWrapping: true,
        autorefresh: true,
        scrollbarStyle: "overlay",
      },
    };
  },
  methods: {
    async submitQuery() {
      let payload = { query: this.code, expand: false };
      await this.$store.dispatch("makeQueryElements", payload).catch((err) => {
        Notify.create({
          color: "negative",
          message: err.message,
        });
      });
    },
  },
};
</script>

<style lang="sass">
.exp-item
  background-color: $accent
  color: white
  border-radius: 2px
  text-align: center

.cm-s-neo.CodeMirror
  background-color: rgb(0, 1, 10)
  font-size: 16px
  filter: brightness(150%)
  border: 1px solid $grey-9
  text-align: left
</style>
