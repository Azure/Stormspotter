<template>
  <div id="cyto">
    <StormCytoscape />
    <DropdownQuery id="dropdown-query" />
    <InfoTabs id="info-tabs" />
    <MenuBar id="menu-bar" />
  </div>
</template>

<script>
import StormCytoscape from "components/StormCytoscape";
import InfoTabs from "components/InfoTabs";
import MenuBar from "components/MenuBar";
import DropdownQuery from "components/DropdownQuery";

export default {
  name: "MainLayout",
  components: { StormCytoscape, InfoTabs, MenuBar, DropdownQuery },
};
</script>
