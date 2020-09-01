<template>
  <div class="q-pa-xs row items-start q-gutter-none">
    <q-list padding class="rounded-borders">
      <q-expansion-item
        v-for="query in queries"
        :key="`${query.title}`"
        dense
        dense-toggle
        expand-separator
        :label="query.title"
      >
        <q-card dark>
          <q-card-section>
            {{ query.cypher }}
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>
  </div>
</template>

<script>
export default {
  name: "QueryView",
  data() {
    return {
      queries: [
        {
          title: "Show All Global Administrators",
          cypher:
            "MATCH (a:AADRole)<-[r:MemberOf]-(t) WHERE a.name = 'Company Administrator' RETURN *",
        },
        {
          title: "Show All AAD Roles",
          cypher: "MATCH (a:AADRole) RETURN *",
        },
        {
          title: "Show All RBAC Relationships",
          cypher: "MATCH (a)-[r]-(t) WHERE EXISTS(r.roleName) RETURN *",
        },
        {
          title: "Show All Owner Relationships",
          cypher: "MATCH (a)-[r]-(t) WHERE r.roleName = 'Owner' RETURN *",
        },
        {
          title: "Show All Contributor Relationships",
          cypher: "MATCH (a)-[r]-(t) WHERE r.roleName = 'Contributor' RETURN *",
        },
        {
          title: "Show All Relationships for Key Vaults",
          cypher: "MATCH (a)-[r]-(t) WHERE a.type = 'KeyVault' RETURN *",
        },
        {
          title: "Show All Service Principals with Cert or Password Counts",
          cypher:
            "MATCH (a:ServicePrincipal) WHERE a.keyCredentialCount > 0 or a.passwordCredentialCount > 0 RETURN *",
        },
      ],
    };
  },
};
</script>
