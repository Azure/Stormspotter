function importAll(r) {
  let images = {};
  r.keys().map((item, index) => {
    images[item.replace("./", "")] = r(item);
  });
  return images;
}

const images = importAll(
  require.context("./assets/nodes", false, /\.(png|jpe?g|svg)$/)
);

const config = {
  wheelSensitivity: 0.2,
  style: [
    {
      selector: "node",
      style: {
        label: "data(name)",
        color: "white",
        "font-size": 8,
        "text-valign": "bottom",
        "text-halign": "center",
        "background-fit": "contain",
        "background-clip": "none",
        "text-background-color": "#00001a",
        "text-background-opacity": 0.7,
        "text-background-padding": 1,
        "text-background-shape": "roundrectangle",
        "min-zoomed-font-size": 8,
        "background-color": "#003366",
        "background-opacity": 0,
        "overlay-color": "white",
        "font-family": "Cascadia Mono",
        "background-image": images["generic.png"],
        "z-index": 10,
      },
    },
    {
      selector: "edge",
      style: {
        width: "2px",
        "target-arrow-shape": "triangle",
        "target-arrow-color": "white",
        "target-arrow-fill": "filled",
        "control-point-step-size": "100px",
        label: "data(type)",
        color: "white",
        "line-color": "#666362",
        "font-size": "8",
        "curve-style": "bezier",
        "text-rotation": "autorotate",
        "text-valign": "top",
        "text-margin-y": -10,
        "text-background-color": "#00001a",
        "min-zoomed-font-size": 8,
        "font-family": "Cascadia Mono",
      },
    },
    {
      selector: ":selected",
      style: {
        "border-opacity": 1,
        opacity: 1,
        color: "#ff7f00",
        "z-index": 9999,
      },
    },
    {
      selector: ".incomingNode",
      style: {
        "background-color": "#0074D9",
        color: "#FC6A03",
        "z-index": 9999,
        opacity: 1,
      },
    },
    {
      selector: ".incomingEdge",
      style: {
        "line-color": "#FC6A03",
        "z-index": 9999,
        opacity: 1,
      },
    },
    {
      selector: ".outgoingNode",
      style: {
        "background-color": "#FF4136",
        color: "#A0FA82",
        "z-index": 9999,
        opacity: 1,
      },
    },
    {
      selector: ".outgoingEdge",
      style: {
        "line-color": "#A0FA82",
        "z-index": 9999,
        opacity: 1,
      },
    },
    {
      selector: ".opacityDim",
      style: {
        "z-index": 9999,
        opacity: 0.3,
      },
    },
    {
      selector: "node[!type]",
      style: {
        "background-image": images["none.png"],
      },
    },
  ],
};

const NODE_LABELS = {
  AADApplication: images["aadapp.png"],
  AADGroup: images["aadgroup.png"],
  AADRole: images["aadrole.png"],
  AADServicePrincipal: images["aadsp.png"],
  AADUser: images["aaduser.png"],
  Disk: images["disks.png"],
  GenericAsset: images["generic.png"],
  IpConfiguration: images["ipconf.png"],
  KeyVault: images["kv.png"],
  LoadBalancer: images["loadb.png"],
  NetworkInterface: images["nic.png"],
  NetworkSecurityGroup: images["nsg.png"],
  PublicIp: images["ip.png"],
  ResourceGroup: images["rg.png"],
  Rule: images["rule.png"],
  ServiceFabric: images["sf.png"],
  ServerFarm: images["serverfarm.png"],
  SQLDatabase: images["sqldb.png"],
  SQLServer: images["sqlserver.png"],
  StorageAccount: images["storage.png"],
  Subscription: images["sub.png"],
  Tenant: images["tenant.png"],
  VirtualMachine: images["vm.png"],
  VirtualNetwork: images["vnet.png"],
  WebSite: images["appservice.png"],
};

for (var [key, value] of Object.entries(NODE_LABELS)) {
  let nodeStyle = {
    selector: `node[type = "${key}"]`,
    style: {
      "background-image": value,
    },
  };
  config.style.push(nodeStyle);
}
export default config;
