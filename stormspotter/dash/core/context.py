import zipfile
import io
import logging
import json
import re
import os
import time
from pathlib import Path
from pprint import pprint
from threading import Thread
from stormspotter.dash.core.neo4j import Neo4j
from stormspotter.dash.core.resources import *
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    
class DashParser:

    def __init__(self, user, password, server):
        self.neo = Neo4j(user=user, password=password, server=server)
        self.tenant = None
        self.data_path = Path(__file__).parents[3].absolute() / "data/input"
        self.processed_path = Path(__file__).parents[3].absolute() / "data/processed"
        self.observer = Observer()

        self.event_handler = FileSystemEventHandler()
        self.event_handler.on_created = self.on_created
        self.observer.schedule(self.event_handler, str(self.data_path))
        self.observer.start()

        self.processExistingFiles()

    def on_created(self, event):
        src = Path(event.src_path)
        if zipfile.is_zipfile(src):
            self.parseInputFile(src)
            os.rename(src, f"{self.processed_path}\\{src.stem}_{time.strftime('%Y%m%d-%H%M%S')}.zip")

    def processExistingFiles(self):        
        for file in self.data_path.iterdir():
            event = self.event_handler.on_created(FileCreatedEvent(str(file)))

    def _parseObject(self, data, fields, objtype):
        obj = {f:data.get(f) for f in fields}
        obj["raw"]= json.dumps(data)
        obj["type"] = objtype
        obj["tags"] = str(data.get("tags"))
        return obj

    def dbSummary(self):
        return self.neo.dbSummary()

    def _parseTenants(self, tenants):
        for tenant in tenants:
            self.tenant = tenant["tenantId"]
            t_fields = ["tenantId", "category", "country", "country", "countryCode",
                        "name", "domains"]
            t = self._parseObject(tenant, t_fields, TENANT_NODE_LABEL)
            t["subscriptionCount"] = len(tenant["subscriptions"])

            self.neo.insert_asset(t, t["type"], t["tenantId"], [GENERIC_NODE_LABEL])

            for sub in tenant["subscriptions"]:
                s_fields = ["id", "name", "spendingLimit", "state"]
                s = self._parseObject(sub, s_fields, SUBSCRIPTION_NODE_LABEL)
                s["resourceGroupCount"] = len(sub["resourceGroups"])

                self.neo.insert_asset(s, s["type"], s["id"], [GENERIC_NODE_LABEL])
                self.neo.create_relationship(t["tenantId"], TENANT_NODE_LABEL,
                                             s["id"], SUBSCRIPTION_NODE_LABEL, DEFAULT_REL)
                for rg in sub["resourceGroups"]:
                    r_fields = ["id", "name", "location", "managedBy"]
                    r = self._parseObject(rg, r_fields, RESOURCEGROUP_NODE_LABEL)
            
                    self.neo.insert_asset(r, r["type"], r["id"], [GENERIC_NODE_LABEL])
                    self.neo.create_relationship(sub["id"], SUBSCRIPTION_NODE_LABEL,
                                                 r["id"], RESOURCEGROUP_NODE_LABEL, DEFAULT_REL)

    def _parseUsers(self, users):
        for aaduser in users:
            u_fields = ["objectId", "userPrincipalName", "onPremisesSecurityIdentifier",
                        "lastPasswordChangeDateTime", "mail", "accountEnabled",
                        "immutableId", "dirSyncEnabled"]
            
            user = self._parseObject(aaduser, u_fields, AADUSER_NODE_LABEL)
            user["name"] = aaduser["displayName"]
            
            self.neo.insert_asset(user, AADOBJECT_NODE_LABEL, user["objectId"], [AADUSER_NODE_LABEL])

    def _parseGroups(self, groups):
        for aadgroup in groups:
            g_fields = ["objectId", "description", "mail", 
                        "dirSyncEnabled", "securityEnabled", "membershipRule",
                        "membershipRuleProcessingState", "onPremisesSecurityIdentifier"]
            
            group = self._parseObject(aadgroup, g_fields, AADGROUP_NODE_LABEL)
            group["name"] = aadgroup["displayName"]
            
            self.neo.insert_asset(group, AADOBJECT_NODE_LABEL, group["objectId"], [AADGROUP_NODE_LABEL])
            for member in aadgroup["members"]:
                self.neo.create_relationship(member, AADOBJECT_NODE_LABEL,
                                             group["objectId"], AADGROUP_NODE_LABEL, USER_TO_GROUP)
            for owner in aadgroup["owners"]:
                self.neo.create_relationship(owner, AADOBJECT_NODE_LABEL, group["objectId"], 
                                             AADGROUP_NODE_LABEL, "Owns")

    def _parseApplications(self, apps):
        for aadapp in apps:
            a_fields = ["objectId", "appId", "homepage", "keyCredentials",
                        "passwordCredentials", "publisherDomain"]
            
            app = self._parseObject(aadapp, a_fields, AADAPP_NODE_LABEL)
            app["name"] = aadapp["displayName"]
            app["passwordCredentialCount"] = len(app.pop("passwordCredentials"))
            app["keyCredentialCount"] = len(app.pop("keyCredentials"))

            self.neo.insert_asset(app, AADOBJECT_NODE_LABEL, app["objectId"], [AADAPP_NODE_LABEL])
            for owner in aadapp["owners"]:
                self.neo.create_relationship(owner, AADOBJECT_NODE_LABEL, app["objectId"],
                                              AADAPP_NODE_LABEL, "Owns")

    def _parseSPs(self, sps):
        for aadsp in sps:
            sp_fields = ["appDisplayName", "objectId", "appId", "accountEnabled",
                         "servicePrincipalNames", "homepage", "passwordCredentials",
                         "keyCredentials", "appOwnerTenantId", "publisherName",
                         "microsoftFirstParty"]

            sp = self._parseObject(aadsp, sp_fields, AADSPN_NODE_LABEL)
            sp["name"] = aadsp["displayName"]
            sp["passwordCredentialCount"] = len(sp.pop("passwordCredentials"))
            sp["keyCredentialCount"] = len(sp.pop("keyCredentials"))

            self.neo.insert_asset(sp, AADOBJECT_NODE_LABEL, sp["objectId"], [AADSPN_NODE_LABEL])
            for owner in aadsp["owners"]:
                self.neo.create_relationship(owner, AADOBJECT_NODE_LABEL, sp["objectId"],
                                            AADSPN_NODE_LABEL, "Owns")

    def _parseGeneric(self, asset):
        gen_fields = ["id", "name"]
        gen = self._parseObject(asset, gen_fields, GENERIC_NODE_LABEL)
        self.neo.insert_asset(gen, GENERIC_NODE_LABEL, gen["id"])

    def _parseKeyVaults(self, vault):
        rgroup = vault["id"].split("/providers")[0]

        prop_fields = ["vaultUri", "enableRbacAuthorization", "enabledForDeployment",
                       "enabledForDiskEncryption", "enableSoftDelete", "softDeleteRetentionInDays",
                       "enabledForTemplateDeployment"]

        kv = self._parseObject(vault["properties"], prop_fields, KEYVAULT_NODE_LABEL)        
        kv["name"] = vault["name"]
        kv["id"] = vault["id"]
        kv["vaultUri"] = kv["vaultUri"].replace("https://", "").rstrip("/")
        kv["accessPolicyCount"] = len(vault["properties"]["accessPolicies"])
        kv["raw"]= json.dumps(vault)

        self.neo.insert_asset(kv, KEYVAULT_NODE_LABEL, kv["id"], [GENERIC_NODE_LABEL])
        self.neo.create_relationship(rgroup, RESOURCEGROUP_NODE_LABEL,
                                     kv["id"], KEYVAULT_NODE_LABEL, DEFAULT_REL)
        for policy in vault["properties"]["accessPolicies"]:
            self.neo.create_relationship(policy["objectId"], AADOBJECT_NODE_LABEL, kv["id"],
                                        KEYVAULT_NODE_LABEL, AAD_TO_KV, to_find_type="MATCH", 
                                        relationship_properties=policy["permissions"])

    def _parsePublicIps(self, ip):
        rgroup = ip["id"].split("/providers")[0]

        pip = {}
        pip["name"] = ip["name"]
        pip["id"] = ip["id"]
        pip["type"] = PUBLIC_IP_NODE_LABEL

        pip["publicIPAllocationMethod"] = ip.get("properties", {}).get("publicIPAllocationMethod", "---")
        pip["fqdn"] = ip.get("properties", {}).get("dnsSettings", {}).get("fqdn", "---")
        pip["ipAddress"] = ip.get("properties", {}).get("ipAddress", "---")
        pip['raw'] = json.dumps(ip)

        self.neo.insert_asset(pip, PUBLIC_IP_NODE_LABEL, pip["id"], [GENERIC_NODE_LABEL])
        self.neo.create_relationship(rgroup, RESOURCEGROUP_NODE_LABEL,
                                pip["id"], PUBLIC_IP_NODE_LABEL, DEFAULT_REL)

    def _parseNSGs(self, nsg):
        rgroup = nsg["id"].split("/providers")[0]
        nsgroup = {}
        nsgroup["name"] = nsg["name"]
        nsgroup["id"] = nsg["id"]
        nsgroup["type"] = NSG_NODE_LABEL
        nsgroup["raw"] = json.dumps(nsg)
        nsgroup["ruleCount"] = len(nsg["properties"]["securityRules"])

        self.neo.insert_asset(nsgroup, NSG_NODE_LABEL, nsgroup["id"])
        for secrule in nsg["properties"]["securityRules"]:
            if secrule["properties"]["access"] == "Allow": 
                rule = {}
                rule["name"] = secrule["name"]
                rule["id"] = secrule["id"]
                rule["description"] = secrule["properties"].get("description", "---")
                rule["direction"] = secrule["properties"].get("direction")
                rule["access"] = "Allow"
                rule["priority"] = secrule["properties"].get("priority")
                rule["protocol"] = json.dumps(secrule["properties"].get("protocol"))
                rule["sourceAddressPrefix"] = secrule["properties"].get("sourceAddressPrefix")
                rule["sourcePortRange"] = secrule["properties"].get("sourcePortRange")
                rule["destinationAddressPrefix"] = secrule["properties"].get("destinationAddressPrefix")
                rule["destinationPortRange"] = secrule["properties"].get("destinationPortRange")

                rule["type"] = RULE_NODE_LABEL
                rule["raw"] = json.dumps(secrule)
                self.neo.insert_asset(rule, RULE_NODE_LABEL, rule["id"], [GENERIC_NODE_LABEL])
                self.neo.create_relationship(nsgroup["id"], NSG_NODE_LABEL, rule["id"], RULE_NODE_LABEL, DEFAULT_REL)
        if netifs := nsg["properties"].get("networkInterfaces"):
            for ni in netifs:
                self.neo.create_relationship(ni["id"], NETWORKINTERFACE_NODE_LABEL, nsg["id"], NSG_NODE_LABEL, NIC_TO_NSG)

    def _parseNetInterfaces(self, netif):
        rgroup = netif["id"].split("/providers")[0]
        nic = {}
        nic["name"] = netif["name"]
        nic["id"] = netif["id"]
        nic["type"] = netif["type"]
        nic["macAddress"] = netif["properties"].get("macAddress")
        nic["ipForwarding"] = netif["properties"]["enableIPForwarding"]
        nic["type"] = NETWORKINTERFACE_NODE_LABEL
        nic["raw"] = json.dumps(netif)
        nic["ipConfigurationCount"] = len(netif["properties"]["ipConfigurations"])
        self.neo.insert_asset(nic, NETWORKINTERFACE_NODE_LABEL, nic["id"])

        vm = ""
        if vm := netif["properties"].get("virtualMachine"):
            self.neo.create_relationship(vm["id"], VIRTUALMACHINE_NODE_LABEL, nic["id"], NETWORKINTERFACE_NODE_LABEL, DEFAULT_REL)
        
        for ipconf in netif["properties"]["ipConfigurations"]:
            conf = {}
            conf["id"] = ipconf["id"]
            conf["name"] = ipconf["name"]
            conf["type"] = IPCONFIG_NODE_LABEL
            conf["primary"] = ipconf["properties"].get("primary")
            conf["privateIPAddress"] = ipconf["properties"].get("privateIPAddress")
            conf["privateIPAllocationMethod"] = ipconf["properties"].get("privateIPAllocationMethod")
            conf["raw"] = json.dumps(ipconf)
            self.neo.insert_asset(conf, IPCONFIG_NODE_LABEL, conf["id"], [GENERIC_NODE_LABEL])

            if publicip := ipconf["properties"].get("publicIPAddress"):
                self.neo.create_relationship(conf["id"], IPCONFIG_NODE_LABEL, publicip["id"], PUBLIC_IP_NODE_LABEL, ASSET_TO_ENDPOINT_OR_IP)

            if subnet := ipconf["properties"].get("subnet"):
                id_list = subnet["id"].split("/")
                subnet_name = id_list[-1]
                vnet_name = id_list[-3]
                vnet_id = "/".join(id_list[:-2])
                vnet = {
                    "id": vnet_id,
                    "name": vnet_name,
                    "subnet": subnet_name,
                    "type": VIRTUALNETWORK_NODE_LABEL
                }
                self.neo.insert_asset(vnet, VIRTUALNETWORK_NODE_LABEL, vnet_id, [GENERIC_NODE_LABEL])
                self.neo.create_relationship(vnet_id, VIRTUALNETWORK_NODE_LABEL, conf["id"], IPCONFIG_NODE_LABEL, IPCONFIG_TO_NIC)
                self.neo.create_relationship(rgroup, RESOURCEGROUP_NODE_LABEL,
                                             vnet_id, VIRTUALNETWORK_NODE_LABEL, DEFAULT_REL)

                if vm:
                    self.neo.create_relationship(vm["id"], VIRTUALMACHINE_NODE_LABEL, vnet_id, VIRTUALNETWORK_NODE_LABEL, ASSET_TO_VNET)

    def _parseLoadBalancers(self, resource):
        lb_fields = []
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = LOADBALANCER_NODE_LABEL
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, LOADBALANCER_NODE_LABEL, obj["id"],[GENERIC_NODE_LABEL] )
    
    def _parseStorageAccounts(self, storage):
        sa_fields = ["id", "kind", "location", "name"]
        sa = self._parseObject(storage, sa_fields, STORAGEACCOUNT_NODE_LABEL)
        sa["accessTier"] = storage["properties"].get("accessTier")
        sa["supportsHttpsTrafficOnly"] = storage["properties"].get("supportsHttpsTrafficOnly", False)
        self.neo.insert_asset(sa, STORAGEACCOUNT_NODE_LABEL, sa["id"], [GENERIC_NODE_LABEL])

    def _parseDisks(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = DISK_NODE_LABEL
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, DISK_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )
    
    def _parseRbacs(self, rbacs):
        for rbac in rbacs:
            rel_props = rbac["roleInfo"]
            rel_props["admintype"] = rbac["admintype"]
            self.neo.create_relationship(rbac["objectId"], AADOBJECT_NODE_LABEL, rbac["roleInfo"]["scope"], GENERIC_NODE_LABEL,
                                         "Admin", relationship_properties=rel_props, relationship_unique_property="assignment", relationship_unique_value=rbac["roleInfo"]["assignment"])

    def _parseServiceFabrics(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = SERVICEFABRIC_NODE_LABEL
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, SERVICEFABRIC_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )

    def _parseServiceBus(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = resource["type"]
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, SERVICEBUSNAMESPACE_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )

    def _parseVMs(self, vm):
        rgroup = vm["id"].split("/providers")[0]
        obj = {"raw": json.dumps(vm)}
        obj["id"] = vm["id"]
        obj["name"] = vm["name"]
        obj["type"] = VIRTUALMACHINE_NODE_LABEL
        if vm["properties"].get("availabilitySet"):
            vmas_id = vm["availabilitySet"]["id"]
            vmas_name = vmas_id.split("/")[-1]
            vmas_asset = {"id": vmas_id, "name": vmas_name}
            self.neo.insert_asset(vmas_asset, AVAILABILITYSET_NODE_LABEL, vmas_id, [GENERIC_NODE_LABEL])
            self.neo.create_relationship(vmas_id, AVAILABILITYSET_NODE_LABEL, vm["id"], VIRTUALMACHINE_NODE_LABEL, DEFAULT_REL)
        else:
            self.neo.insert_asset(obj, VIRTUALMACHINE_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL])

    def _parseDomainNames(self, names):
        pass

    def _parseSqlServers(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = SQLSERVER_NODE_LABEL
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, SQLSERVER_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )

    def _parseSqlDbs(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = SQLDATABASE_NODE_LABEL
        if name := resource.get("name"):
            obj["name"] = resource["name"]
        self.neo.insert_asset(obj, SQLDATABASE_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )

    def _parseWebsites(self, resource):
        obj = {"raw": json.dumps(resource)}
        obj["id"] = resource["id"]
        obj["type"] = WEBSITE_NODE_LABEL
        obj["name"] = resource["name"]
        obj["kind"] = resource["kind"]
        self.neo.insert_asset(obj, WEBSITE_NODE_LABEL, obj["id"], [GENERIC_NODE_LABEL] )


    def parseInputFile(self, filename):
        validAAD = {
            "AADUser.json": self._parseUsers,
            "AADGroup.json": self._parseGroups,
            "AADApplication.json": self._parseApplications,
            "AADServicePrincipal.json": self._parseSPs
        }
        
        validAzure = {
            "microsoft.keyvault/vaults": self._parseKeyVaults,
            "microsoft.network/publicipaddresses": self._parsePublicIps,
            "microsoft.network/networksecuritygroups": self._parseNSGs,
            "microsoft.network/networkinterfaces": self._parseNetInterfaces,
            "microsoft.network/loadbalancers": self._parseLoadBalancers,
            "microsoft.storage/storageaccounts": self._parseStorageAccounts,
            "microsoft.compute/disks": self._parseDisks,
            "microsoft.servicefabric/clusters": self._parseServiceFabrics,
            "microsoft.servicebus/namespaces": self._parseServiceBus,
            "microsoft.compute/virtualmachines": self._parseVMs,
            "microsoft.classiccompute/domainnames": self._parseDomainNames,
            "microsoft.sql/servers": self._parseSqlServers,
            "microsoft.sql/servers/databases": self._parseSqlDbs, 
            "microsoft.web/sites": self._parseWebsites
        }
        with zipfile.ZipFile(filename) as memzip:
            filelist = memzip.namelist()
            if tenants := memzip.read("subdata.json"):
                self._parseTenants(json.loads(tenants))

            aadfiles = list(filter(lambda x: x in validAAD.keys(), filelist))
            for aad in aadfiles:
                aadobjects = memzip.read(aad)
                validAAD[aad](json.loads(aadobjects))

            guid = re.compile("^([0-9A-Fa-f]{8}[-][0-9A-Fa-f]{4}[-][0-9A-Fa-f]{4}[-][0-9A-Fa-f]{4}[-][0-9A-Fa-f]{12})\.json$")
            subfiles = list(filter(lambda x: guid.match(x), filelist))
            for sub in subfiles:
                subresources = json.loads(memzip.read(sub))
                for resource in subresources:
                    if resource:
                        if resource["type"].lower() in validAzure.keys():
                            validAzure[resource['type'].lower()](resource)
                        else:
                            self._parseGeneric(resource)
            
            if rbacs := memzip.read("rbac.json"):
                self._parseRbacs(json.loads(rbacs))

        self.finalize()

    def finalize(self):
        finals = ["MATCH (vm:VirtualMachine)-[:CONTAINS]->(n:NetworkInterface)-[:EXPOSES]->(pip:Ip) WHERE exists(pip.ipAddress) MATCH (n)-[:USES]->(nsg:NetworkSecurityGroup)-[:CONTAINS]->(r:Rule) MERGE (vm)-[:EXPOSES]->(Endpoint{endpoint:pip.ipAddress+':'+r.port, virtualmachine:vm.id})",
                  "MATCH (a:AvailabilitySet)-[:CONTAINS]->(vm:VirtualMachine)-[:CONTAINS]->(n:NetworkInterface) MATCH (p:Pool) WHERE n.id IN p.ipconfigs MERGE (p)-[:OFTYPE]->(a)"]

        for f in finals:
            self.neo.query(f)
        print("done")

    def query_build(self, name, key, value):
        query = "MATCH (n"
        query += f":{name}) " if name != "Any" else ")"
        query += f"WHERE n.{key} = {value} " if key not in ["NONE", None] and value else " "
        query += "RETURN n"
        return self.neo.query(query, True)

    def getQuery(self, query=None, fquery=None):
        elements = []
        if query:
            result = self.neo.query(query, True)
        elif fquery:
            result = self.query_build(*fquery)

        for res in result.values():
            for r in res:
                if hasattr(r, "start"):
                    data = {"data": {"source": r.start, 
                                     "target": r.end,
                                     "sourceName": r.start_node["name"] or r.start_node["id"],
                                     "targetName": r.end_node["name"] or r.end_node["id"],
                                     "label": r.type,
                                     "properties": {k:v for k,v in r.items()}}}
                else:
                    nodeDict = {k:v for k, v in r.items()}
                    nodeDict["id"] = r.id
                    nodeDict["label"] = r["name"] or r["id"]
                    nodeDict["raw"] = r["raw"] or json.dumps({"objectId": r["id"]})

                    data = {"data": nodeDict}
            
                data["classes"] = ""
                elements.append(data)
        return [v for idx, v in enumerate(elements) if v not in elements[idx+1:]]  
        