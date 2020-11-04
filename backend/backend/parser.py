import asyncio
import os
import shutil
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile, mkdtemp
from typing import Any, List

import aiofiles
import aiosqlite
import orjson
from loguru import logger

from .db import Neo4j
from .resources import *


class SSProcessor:
    def __init__(self) -> None:
        self.neo = None
        self._aad_methods = {
            "Application": self._parseAADApplication,
            "Group": self._parseAADGroup,
            "Role": self._parseAADRole,
            "ServicePrincipal": self._parseAADServicePrincipal,
            "User": self._parseAADUser,
        }
        self._arm_methods = {
            "microsoft.compute/disks": self._parseDisk,
            "microsoft.compute/virtualmachines": self._parseVirtualMachine,
            "microsoft.keyvault/vaults": self._parseKeyVault,
            "microsoft.network/loadbalancers": self._parseLoadBalancer,
            "microsoft.network/networkinterfaces": self._parseNetInterface,
            "microsoft.network/networksecuritygroups": self._parseNSG,
            "microsoft.network/publicipaddresses": self._parsePublicIp,
            "microsoft.servicefabric/clusters": self._parseServiceFabric,
            "microsoft.sql/servers": self._parseSqlServer,
            "microsoft.sql/servers/databases": self._parseSqlDb,
            "microsoft.storage/storageaccounts": self._parseStorageAccount,
            "microsoft.web/serverfarms": self._parseServerFarm,
            "microsoft.web/sites": self._parseWebsite,
            "microsoft.servicebus/namespaces": self._parseServiceBus,
        }

    @logger.catch
    async def _parseProperty(self, value: Any) -> Any:
        if isinstance(value, (str, int, bool)):
            return value
        elif isinstance(value, list):
            if len(value) and all(isinstance(item, (str, int, bool)) for item in value):
                return value
            # Need to either flatten dicts or reject them outright and rely on raw field
            elif len(value) and any(isinstance(item, dict) for item in value):
                pass
        elif isinstance(value, dict):
            # Need to either flatten dicts or reject them outright and rely on raw field
            pass

    @logger.catch
    async def _postProcessResource(self, resource: dict) -> dict:
        resource_attrs = {
            k: await self._parseProperty(v) for k, v in resource.items() if k != "raw"
        }
        resource_attrs["raw"] = resource["raw"]

        resource_props = {}
        if resource.get("properties"):
            for k, v in resource.get("properties").items():
                if parsedV := await self._parseProperty(v):
                    resource_props[k] = parsedV

        if resource_props:
            del resource_attrs["properties"]

        return {**resource_attrs, **resource_props}

    async def _parseObject(self, data: dict, fields: List[str], label: str) -> dict:
        parsed = {f.split("@")[0]: data.get(f) for f in fields}
        parsed["raw"] = orjson.dumps(data).decode()
        parsed["type"] = label

        tags = []
        if dataTags := data.get("tags"):
            if isinstance(dataTags, dict):
                for k, v in dataTags.items():
                    tags.extend([k, v])
            elif isinstance(dataTags, list):
                tags.append(dataTags)

        if dn := parsed.get("displayName"):
            parsed["name"] = dn
            del parsed["displayName"]

        if dn := parsed.get("display_name"):
            parsed["name"] = dn
            del parsed["display_name"]

        parsed["tags"] = tags
        return parsed

    @logger.catch
    async def _parseAADUser(self, user: dict):
        parsed = await self._parseObject(user, user.keys(), AADUSER_NODE_LABEL)
        post_user = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_user, AADOBJECT_NODE_LABEL, post_user["objectId"], [AADUSER_NODE_LABEL]
        )

    @logger.catch
    async def _parseAADGroup(self, group: dict):
        parsed = await self._parseObject(group, group.keys(), AADGROUP_NODE_LABEL)
        post_group = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_group,
            AADOBJECT_NODE_LABEL,
            post_group["objectId"],
            [AADGROUP_NODE_LABEL],
        )
        for member in group["members"]:
            self.neo.create_relationship(
                member,
                AADOBJECT_NODE_LABEL,
                post_group["objectId"],
                AADGROUP_NODE_LABEL,
                USER_TO_GROUP,
            )
        for owner in group["owners"]:
            self.neo.create_relationship(
                owner,
                AADOBJECT_NODE_LABEL,
                post_group["objectId"],
                AADGROUP_NODE_LABEL,
                "Owns",
            )

    @logger.catch
    async def _parseAADRole(self, role: dict):
        parsed = await self._parseObject(role, role.keys(), AADROLE_NODE_LABEL)
        post_role = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_role,
            AADOBJECT_NODE_LABEL,
            post_role["objectId"],
            [AADROLE_NODE_LABEL],
        )
        for member in role["members"]:
            self.neo.create_relationship(
                member,
                AADOBJECT_NODE_LABEL,
                post_role["objectId"],
                AADROLE_NODE_LABEL,
                USER_TO_GROUP,
            )

    @logger.catch
    async def _parseAADApplication(self, app: dict):
        parsed = await self._parseObject(app, app.keys(), AADAPP_NODE_LABEL)
        parsed["passwordCredentialCount"] = len(app.get("passwordCredentials", 0))
        parsed["keyCredentialCount"] = len(app.get("keyCredentials", 0))
        post_app = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_app, AADOBJECT_NODE_LABEL, post_app["objectId"], [AADAPP_NODE_LABEL]
        )
        for owner in app["owners"]:
            self.neo.create_relationship(
                owner,
                AADOBJECT_NODE_LABEL,
                post_app["objectId"],
                AADAPP_NODE_LABEL,
                OWNER,
            )

    @logger.catch
    async def _parseAADServicePrincipal(self, spn: dict):
        parsed = await self._parseObject(spn, spn.keys(), AADSPN_NODE_LABEL)
        parsed["passwordCredentialCount"] = len(spn.get("passwordCredentials", 0))
        parsed["keyCredentialCount"] = len(spn.get("keyCredentials", 0))
        post_spn = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_spn, AADOBJECT_NODE_LABEL, post_spn["objectId"], [AADSPN_NODE_LABEL]
        )

        for owner in spn["owners"]:
            self.neo.create_relationship(
                owner,
                AADOBJECT_NODE_LABEL,
                post_spn["objectId"],
                AADSPN_NODE_LABEL,
                OWNER,
            )

    @logger.catch
    async def _processTenant(self, tenant: dict):
        t_fields = [
            "id",
            "tenant_id",
            "tenant_category",
            "display_name",
            "country",
            "countryCode",
            "name",
            "domains",
        ]

        parsed = await self._parseObject(tenant, t_fields, TENANT_NODE_LABEL)
        parsed["subscriptionCount"] = len(tenant["subscriptions"])
        post_tenant = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_tenant, post_tenant["type"], post_tenant["id"], [GENERIC_NODE_LABEL]
        )

        for subscription in tenant["subscriptions"]:
            s_fields = [
                "authorization_source",
                "subscription_id",
                "id",
                "display_name",
                "spendingLimit",
                "state",
                "managed_by_tenants",
            ]
            sub = await self._parseObject(
                subscription, s_fields, SUBSCRIPTION_NODE_LABEL
            )
            sub["resourceGroupCount"] = len(subscription["resourceGroups"])

            post_sub = await self._postProcessResource(sub)
            self.neo.insert_asset(
                post_sub, post_sub["type"], post_sub["id"], [GENERIC_NODE_LABEL]
            )
            self.neo.create_relationship(
                post_tenant["id"],
                TENANT_NODE_LABEL,
                post_sub["id"],
                SUBSCRIPTION_NODE_LABEL,
                DEFAULT_REL,
            )

            for resGroup in subscription["resourceGroups"]:
                r_fields = ["id", "name", "location"]
                rg = await self._parseObject(
                    resGroup, r_fields, RESOURCEGROUP_NODE_LABEL
                )
                post_rg = await self._postProcessResource(rg)

                self.neo.insert_asset(
                    post_rg, post_rg["type"], post_rg["id"], [GENERIC_NODE_LABEL]
                )
                self.neo.create_relationship(
                    post_sub["id"],
                    SUBSCRIPTION_NODE_LABEL,
                    post_rg["id"],
                    RESOURCEGROUP_NODE_LABEL,
                    DEFAULT_REL,
                )

    @logger.catch
    async def _parseDisk(self, disk: dict, rgroup: str):
        parsed = await self._parseObject(disk, disk.keys(), DISK_NODE_LABEL)
        post_disk = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_disk, DISK_NODE_LABEL, post_disk["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_disk["id"],
            DISK_NODE_LABEL,
            DEFAULT_REL,
        )

        if ownerid := disk.get("ownerId"):
            self.neo.create_relationship(
                ownerid,
                VIRTUALMACHINE_NODE_LABEL,
                post_disk["id"],
                DISK_NODE_LABEL,
                ATTACHED_TO_ASSET,
            )

    @logger.catch
    async def _parseGeneric(self, generic: dict, rgroup: str):
        parsed = await self._parseObject(generic, generic.keys(), GENERIC_NODE_LABEL)
        post_generic = await self._postProcessResource(parsed)

        self.neo.insert_asset(post_generic, GENERIC_NODE_LABEL, post_generic["id"])
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_generic["id"],
            GENERIC_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseKeyVault(self, kv: dict, rgroup: str):
        parsed = await self._parseObject(kv, kv.keys(), KEYVAULT_NODE_LABEL)
        post_kv = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_kv, KEYVAULT_NODE_LABEL, post_kv["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_kv["id"],
            KEYVAULT_NODE_LABEL,
            DEFAULT_REL,
        )

        for policy in kv["properties"]["accessPolicies"]:
            self.neo.create_relationship(
                policy["objectId"],
                AADOBJECT_NODE_LABEL,
                post_kv["id"],
                KEYVAULT_NODE_LABEL,
                HAS_PERMISSIONS,
                to_find_type="MATCH",
                relationship_properties=policy["permissions"],
            )

    @logger.catch
    async def _parseLoadBalancer(self, lb: dict, rgroup: str):
        # TODO Verify LB JSON
        parsed = await self._parseObject(lb, lb.keys(), LOADBALANCER_NODE_LABEL)
        post_lb = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_lb, LOADBALANCER_NODE_LABEL, post_lb["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_lb["id"],
            LOADBALANCER_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parsePublicIp(self, pip: dict, rgroup: str):
        parsed = await self._parseObject(pip, pip.keys(), PUBLIC_IP_NODE_LABEL)
        post_pip = await self._postProcessResource(parsed)

        post_pip["fqdn"] = pip.get("properties", {}).get("dnsSettings", {}).get("fqdn")
        self.neo.insert_asset(
            post_pip, PUBLIC_IP_NODE_LABEL, post_pip["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_pip["id"],
            PUBLIC_IP_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseNSG(self, nsg: dict, rgroup: str):
        parsed = await self._parseObject(nsg, nsg.keys(), NSG_NODE_LABEL)
        post_nsg = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_nsg, NSG_NODE_LABEL, post_nsg["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_nsg["id"],
            NSG_NODE_LABEL,
            DEFAULT_REL,
        )

        for secrule in nsg["properties"]["securityRules"]:
            if secrule["properties"]["access"] == "Allow":
                parsed_rule = await self._parseObject(
                    secrule, secrule.keys(), RULE_NODE_LABEL
                )
                post_rule = await self._postProcessResource(parsed_rule)

                self.neo.insert_asset(
                    post_rule, RULE_NODE_LABEL, post_rule["id"], [GENERIC_NODE_LABEL]
                )
                self.neo.create_relationship(
                    post_nsg["id"],
                    NSG_NODE_LABEL,
                    post_rule["id"],
                    RULE_NODE_LABEL,
                    ASSET_TO_ENDPOINT_OR_IP,
                )

        if netifs := nsg["properties"].get("networkInterfaces"):
            for ni in netifs:
                parsed_ni = await self._parseObject(ni, ni.keys(), RULE_NODE_LABEL)
                post_ni = await self._postProcessResource(parsed_ni)
                self.neo.create_relationship(
                    post_ni["id"],
                    NETWORKINTERFACE_NODE_LABEL,
                    post_nsg["id"],
                    NSG_NODE_LABEL,
                    NIC_TO_NSG,
                )

    @logger.catch
    async def _parseNetInterface(self, ni: dict, rgroup: str):
        parsed = await self._parseObject(ni, ni.keys(), NETWORKINTERFACE_NODE_LABEL)
        post_ni = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_ni, NETWORKINTERFACE_NODE_LABEL, post_ni["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_ni["id"],
            NETWORKINTERFACE_NODE_LABEL,
            DEFAULT_REL,
        )

        vm = None
        if vm := ni["properties"].get("virtualMachine"):
            self.neo.create_relationship(
                vm["id"],
                VIRTUALMACHINE_NODE_LABEL,
                post_ni["id"],
                NETWORKINTERFACE_NODE_LABEL,
                ATTACHED_TO_ASSET,
            )

        for ipconf in ni["properties"]["ipConfigurations"]:
            parsed_conf = await self._parseObject(
                ipconf, ipconf.keys(), IPCONFIG_NODE_LABEL
            )
            post_conf = await self._postProcessResource(parsed_conf)

            self.neo.insert_asset(
                post_conf, IPCONFIG_NODE_LABEL, post_conf["id"], [GENERIC_NODE_LABEL]
            )
            if publicip := ipconf["properties"].get("publicIPAddress"):
                self.neo.create_relationship(
                    post_conf["id"],
                    IPCONFIG_NODE_LABEL,
                    publicip["id"],
                    PUBLIC_IP_NODE_LABEL,
                    ASSET_TO_ENDPOINT_OR_IP,
                )

            if subnet := ipconf["properties"].get("subnet"):
                id_list = subnet["id"].split("/")
                subnet_name = id_list[-1]
                vnet_name = id_list[-3]
                vnet_id = "/".join(id_list[:-2])
                vnet = {
                    "id": vnet_id,
                    "name": vnet_name,
                    "subnet": subnet_name,
                    "type": VIRTUALNETWORK_NODE_LABEL,
                }
                self.neo.insert_asset(
                    vnet, VIRTUALNETWORK_NODE_LABEL, vnet_id, [GENERIC_NODE_LABEL]
                )
                self.neo.create_relationship(
                    vnet_id,
                    VIRTUALNETWORK_NODE_LABEL,
                    post_conf["id"],
                    IPCONFIG_NODE_LABEL,
                    IPCONFIG_TO_NIC,
                )
                self.neo.create_relationship(
                    rgroup,
                    RESOURCEGROUP_NODE_LABEL,
                    vnet_id,
                    VIRTUALNETWORK_NODE_LABEL,
                    DEFAULT_REL,
                )

                if vm:
                    self.neo.create_relationship(
                        vm["id"],
                        VIRTUALMACHINE_NODE_LABEL,
                        vnet_id,
                        VIRTUALNETWORK_NODE_LABEL,
                        ASSET_TO_VNET,
                    )

    @logger.catch
    async def _parseRbac(self, rbac: dict):
        rbac_props = rbac["permissions"][0]
        rbac_props["roleName"] = rbac["roleName"]
        rbac_props["roleType"] = rbac["roleType"]
        rbac_props["roleDescription"] = rbac["roleDescription"]

        self.neo.create_relationship(
            rbac["principal_id"],
            AADOBJECT_NODE_LABEL,
            rbac["scope"],
            GENERIC_NODE_LABEL,
            "".join(rbac["roleName"].split()),
            relationship_properties=rbac_props,
            relationship_unique_property=rbac["id"],
        )

    @logger.catch
    async def _parseServerFarm(self, farm: dict, rgroup: str):
        prepped = {**farm, **{k: v for k, v in farm["sku"].items() if k != "name"}}
        parsed = await self._parseObject(prepped, prepped.keys(), SERVERFARM_NODE_LABEL)
        post_farm = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_farm, SERVERFARM_NODE_LABEL, post_farm["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_farm["id"],
            SERVERFARM_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseServiceFabric(self, fabric: dict, rgroup: str):
        parsed = await self._parseObject(
            fabric, fabric.keys(), SERVICEFABRIC_NODE_LABEL
        )
        post_fabric = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_fabric,
            SERVICEFABRIC_NODE_LABEL,
            post_fabric["id"],
            [GENERIC_NODE_LABEL],
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_fabric["id"],
            SERVICEFABRIC_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseServiceBus(self, bus: dict, rgroup: str):
        parsed = await self._parseObject(
            bus, bus.keys(), SERVICEBUSNAMESPACE_NODE_LABEL
        )
        post_bus = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_bus,
            SERVICEBUSNAMESPACE_NODE_LABEL,
            post_bus["id"],
            [GENERIC_NODE_LABEL],
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_bus["id"],
            SERVICEBUSNAMESPACE_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseSqlServer(self, server: dict, rgroup: str):
        print(server)
        parsed = await self._parseObject(server, server.keys(), SQLSERVER_NODE_LABEL)
        post_server = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_server, SQLSERVER_NODE_LABEL, post_server["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_server["id"],
            SQLSERVER_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseSqlDb(self, db: dict, rgroup: str):
        parsed = await self._parseObject(db, db.keys(), SQLDATABASE_NODE_LABEL)
        post_db = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_db, SQLDATABASE_NODE_LABEL, post_db["id"], [GENERIC_NODE_LABEL]
        )

        if serverid := db.get("managedBy"):
            self.neo.create_relationship(
                serverid,
                SQLSERVER_NODE_LABEL,
                post_db["id"],
                SQLDATABASE_NODE_LABEL,
                ASSET_TO_MANAGED,
            )
        else:
            self.neo.create_relationship(
                rgroup,
                RESOURCEGROUP_NODE_LABEL,
                post_db["id"],
                SQLDATABASE_NODE_LABEL,
                DEFAULT_REL,
            )

    @logger.catch
    async def _parseStorageAccount(self, storage: dict, rgroup: str):
        parsed = await self._parseObject(
            storage, storage.keys(), STORAGEACCOUNT_NODE_LABEL
        )
        post_storage = await self._postProcessResource(parsed)

        post_storage["primaryEndpoints"] = list(
            storage["properties"]["primaryEndpoints"].values()
        )
        self.neo.insert_asset(
            post_storage,
            STORAGEACCOUNT_NODE_LABEL,
            post_storage["id"],
            [GENERIC_NODE_LABEL],
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_storage["id"],
            STORAGEACCOUNT_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseVirtualMachine(self, vm: dict, rgroup: str):
        parsed = await self._parseObject(vm, vm.keys(), VIRTUALMACHINE_NODE_LABEL)
        post_vm = await self._postProcessResource(parsed)

        # TODO: Parse VM JSON
        if vm["properties"].get("availabilitySet"):
            vmas_id = vm["properties"]["availabilitySet"]["id"]
            vmas_name = vmas_id.split("/")[-1]
            vmas_asset = {"id": vmas_id, "name": vmas_name}
            self.neo.insert_asset(
                vmas_asset, AVAILABILITYSET_NODE_LABEL, vmas_id, [GENERIC_NODE_LABEL]
            )
            self.neo.create_relationship(
                vmas_id,
                AVAILABILITYSET_NODE_LABEL,
                vm["id"],
                VIRTUALMACHINE_NODE_LABEL,
                DEFAULT_REL,
            )

        else:
            self.neo.insert_asset(
                post_vm, VIRTUALMACHINE_NODE_LABEL, post_vm["id"], [GENERIC_NODE_LABEL]
            )

        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_vm["id"],
            VIRTUALMACHINE_NODE_LABEL,
            DEFAULT_REL,
        )

    @logger.catch
    async def _parseWebsite(self, site: dict, rgroup: str):
        parsed = await self._parseObject(site, site.keys(), WEBSITE_NODE_LABEL)
        post_site = await self._postProcessResource(parsed)

        self.neo.insert_asset(
            post_site, WEBSITE_NODE_LABEL, post_site["id"], [GENERIC_NODE_LABEL]
        )
        self.neo.create_relationship(
            rgroup,
            RESOURCEGROUP_NODE_LABEL,
            post_site["id"],
            WEBSITE_NODE_LABEL,
            DEFAULT_REL,
        )

        if serverfarmid := site["properties"].get("serverFarmId"):
            self.neo.create_relationship(
                serverfarmid,
                SERVERFARM_NODE_LABEL,
                post_site["id"],
                WEBSITE_NODE_LABEL,
                DEFAULT_REL,
            )

    async def _process_json(self, json):
        res = orjson.loads(json)

        if res.get("id") and res.get("id").startswith("/tenants"):
            await self._processTenant(res)

        # AAD OBJECTS
        elif objtype := res.get("objectType"):
            await self._aad_methods[objtype](res)

        # ARM OBJECTS
        elif res.get("type"):
            objtype = res.get("type").lower()
            res["type"] = objtype

            if objtype == "microsoft.authorization/roleassignments":
                await self._parseRbac(res)
            elif objtype in self._arm_methods.keys():
                resource_group = res["id"].split("/providers")[0]
                await self._arm_methods[objtype](res, resource_group)
            else:
                resource_group = res["id"].split("/providers")[0]
                await self._parseGeneric(res, resource_group)

    @logger.catch
    async def is_sqlite(self, file: Path):
        async with aiofiles.open(str(file), "rb") as f:
            sixteen = await f.read(16)
            return sixteen == b"SQLite format 3\000"

    @logger.catch
    async def process_sqlite(self, sql_file: Path):
        logger.info(f"Processing {sql_file.stem} ")
        try:
            async with aiosqlite.connect(sql_file) as db:
                async with db.execute("SELECT * from results") as cursor:
                    while row := await cursor.fetchone():
                        await self._process_json(row[1])
            logger.info(f"Finished processing {sql_file.name} ")
        except Exception as e:
            logger.error(e)

    async def process(
        self, upload: SpooledTemporaryFile, filename: str, neo_user: str, neo_pass: str
    ):

        server = (
            "bolt://stormspotter-neo4j:7687"
            if os.environ.get("DOCKER_STORMSPOTTER")
            else "bolt://localhost:7687"
        )
        # TODO: Pass whole neo4j params from frontend or use .env for server
        self.neo = Neo4j(server=server, user=neo_user, password=neo_pass)
        if zipfile.is_zipfile(upload):
            self.status = f"Unzipping {filename}"
            tempdir = mkdtemp()
            zipfile.ZipFile(upload).extractall(tempdir)
            sqlite_files = [
                f for f in Path(tempdir).glob("*") if await self.is_sqlite(f)
            ]
            await asyncio.gather(*[self.process_sqlite(s) for s in sqlite_files])

            shutil.rmtree(tempdir)

        # Match SPNs with their apps
        self.neo.query(
            f"MATCH (sp:AADServicePrincipal) with sp MATCH (app:AADApplication{{appId:sp.appId}}) MERGE (app)-[:{APP_TO_SPN}]->(sp)"
        )

        # This is to deal with unknown objects that resulted from enumerated objects
        self.neo.query("MATCH (n) WHERE n.name IS NULL SET n.name = n.id")

        logger.info(f"Completed ingestion of {filename}")
