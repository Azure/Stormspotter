<template>
  <q-layout>
    <q-page-container>
      <q-page
        class="window-height window-width row justify-center items-center"
        style="background: black; overflow: hidden;"
      >
        <q-parallax :height="windowHeight">
          <template v-slot:media>
            <video width="100%" height="100%" autoplay loop muted>
              <source type="video/mp4" src="clouds.mp4" />
            </video>
          </template>
          <div class="column q-pa-lg">
            <div class="row">
              <img
                src="logo.png"
                class="q-px-lg"
                style="width: auto; height: auto;"
              />
              <q-card class="text-white" style="background-color: transparent;">
                <!-- <q-card-section class="accent-bg">

                </q-card-section> -->
                <q-card-section style="background-color: transparent;">
                  <q-form
                    class="q-px-sm q-pt-xl q-pb-lg q-mb-none q-mt-xl"
                    ref="loginForm"
                    @submit.prevent.stop="onSubmit"
                  >
                    <q-input
                      class="input-border-bluegrey q-pa-none q-mb-lg"
                      dense
                      style="background-color: transparent;"
                      v-model="username"
                      type="username"
                      label="Username"
                      label-color="grey"
                      :rules="[(username) => !!username || 'Field is required']"
                    >
                      <template v-slot:prepend>
                        <q-icon name="person" color="white" />
                      </template>
                    </q-input>
                    <q-separator vertical inset />
                    <q-input
                      class="input-border-bluegrey q-pa-none q-mb-lg"
                      v-model="password"
                      type="password"
                      dense
                      label="Password"
                      label-color="grey"
                      :rules="[(password) => !!password || 'Field is required']"
                    >
                      <template v-slot:prepend>
                        <q-icon name="lock" color="white" />
                      </template>
                    </q-input>
                    <q-separator vertical inset />
                    <q-input
                      class="input-border-bluegrey q-pa-none q-mb-lg"
                      v-model="server"
                      type="url"
                      label="Server"
                      label-color="grey"
                      :rules="[(url) => !!url || 'Field is required']"
                    >
                      <template v-slot:prepend>
                        <q-icon name="mediation" color="white" />
                      </template>
                    </q-input>
                    <q-checkbox
                      v-model="remember"
                      keep-color
                      label="Remember Me"
                      color="red-10"
                      class="q-pb-none q-ma-xs"
                    />
                    <q-card-actions class="q-px-xs q-pb-none q-ma-xs">
                      <q-btn
                        size="lg"
                        type="submit"
                        color="red-10"
                        class="full-width text-white"
                        label="Spot the Storm"
                        :disabled="submitted"
                      />
                    </q-card-actions>
                  </q-form>
                </q-card-section>
              </q-card>
            </div>
          </div>
        </q-parallax>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script>
import { mapState } from "vuex";

export default {
  name: "Login",
  data() {
    return {
      windowHeight: 1080,
      server: "bolt://localhost:7687",
      username: "neo4j",
      password: "",
      remember: false,
      submitted: false,
    };
  },
  computed: mapState([
    "ssneo4j_user",
    "ssneo4j_pass",
    "ssneo4j_host",
    "ssneo4j_port",
    "ssneo4j_scheme",
  ]),

  created() {
    this.$nextTick(() => {
      window.addEventListener("resize", this.onResize);
    });

    if (
      this.ssneo4j_user &&
      this.ssneo4j_pass &&
      this.$store.getters.isLoggedIn
    ) {
      this.$neo4j.connect(
        this.ssneo4j_scheme,
        this.ssneo4j_host,
        this.ssneo4j_port,
        this.ssneo4j_user,
        this.ssneo4j_pass
      );

      const session = this.$neo4j.getSession();

      session.run("MATCH () RETURN 1 LIMIT 1").then((driver) => {
        this.$store.dispatch("loggedIn");
        this.$router.push("/dashboard");
      });
    }
  },
  beforeDestroy() {
    window.removeEventListener("resize", this.onResize);
  },

  methods: {
    onResize() {
      this.windowHeight = window.outerHeight;
    },

    onSubmit() {
      this.submitted = true;
      this.$refs.loginForm
        .validate()
        .then((driver) => {
          this.connect();
        })
        .catch((err) => {
          this.$q.notify({ color: "red", message: err.message });
          this.submitted = false;
        });
    },

    connect() {
      var scheme = this.server.split("://")[0];
      var hostname = this.server.split("://")[1];
      var host = hostname.split(":")[0];
      var port = hostname.split(":")[1];
      this.$neo4j.connect("bolt", host, port, this.username, this.password);
      const session = this.$neo4j.getSession();

      session
        .run("MATCH () RETURN 1 LIMIT 1")
        .then((driver) => {
          this.$q.notify({
            color: "positive",
            message: "You have been successfully logged in.",
          });

          var payload = {
            user: this.username,
            pass: this.password,
            host: host,
            port: port,
            scheme: scheme,
            remember: this.remember,
          };
          this.$store.dispatch("setAuth", payload);
          this.$router.push("/dashboard");
        })
        .catch((err) => {
          this.$q.notify({ color: "red", message: "Login Failed" });
          this.submitted = false;
        });
    },
    driver() {
      // Get a driver instance
      return this.$neo4j.getDriver();
    },
    testQuery() {
      // Get a session from the driver
      const session = this.$neo4j.getSession();

      // Or you can just call this.$neo4j.run(cypher, params)
      session
        .run("MATCH (n) RETURN count(n) AS count")
        .then((res) => {})
        .then(() => {
          session.close();
        });
    },
  },
};
</script>

<style lang="sass">
body
  color: grey !important

input
  color: white !important

video
  filter: brightness(20%)
</style>
