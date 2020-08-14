import asyncio
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
            "User": self._processAADUser,
            "Group": self._processAADGroup,
            "ServicePrincipal": self._parseAADServicePrincipal,
            "Application": self._parseAADApplication,
        }

    @logger.catch
    async def _parseProperty(self, value: Any) -> Any:
        if isinstance(value, (str, int, bool)):
            return value
        elif isinstance(value, list):
            if len(value) and all(isinstance(item, (str, int, bool)) for item in value):
                return value
            elif len(value) and any(isinstance(item, dict) for item in value):
                return orjson.dumps(value).decode()
        elif isinstance(value, dict):
            return orjson.dumps(value)

    @logger.catch
    async def _postProcessResource(self, resource) -> dict:
        resource_attrs = {
            k: await self._parseProperty(v) for k, v in resource.items() if k != "raw"
        }
        resource_props = (
            {
                k: await self._parseProperty(v)
                for k, v in resource.get("properties").items()
            }
            if resource.get("properties")
            else {}
        )

        return {**resource_attrs, **resource_props}

    async def _parseObject(self, data: dict, fields: List[str], label: str) -> dict:
        data = {f: data.get(f) for f in fields}
        data["raw"] = orjson.dumps(data).decode()
        data["type"] = label
        data["tags"] = str(data.get("tags"))
        return data

    @logger.catch
    async def _processAADUser(self, user: dict):
        u_fields = [
            "objectId",
            "userPrincipalName",
            "onPremisesSecurityIdentifier",
            "lastPasswordChangeDateTime",
            "mail",
            "accountEnabled",
            "immutableId",
            "dirSyncEnabled",
        ]

        parsed = await self._parseObject(user, u_fields, AADUSER_NODE_LABEL)
        post_user = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_user, AADOBJECT_NODE_LABEL, post_user["objectId"], [AADUSER_NODE_LABEL]
        )

    @logger.catch
    async def _processAADGroup(self, group: dict):
        g_fields = [
            "objectId",
            "description",
            "mail",
            "dirSyncEnabled",
            "securityEnabled",
            "membershipRule",
            "membershipRuleProcessingState",
            "onPremisesSecurityIdentifier",
        ]

        parsed = await self._parseObject(group, g_fields, AADGROUP_NODE_LABEL)
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
    async def _parseAADApplication(self, app: dict):
        a_fields = [
            "objectId",
            "appId",
            "homepage",
            "keyCredentials",
            "passwordCredentials",
            "publisherDomain",
        ]

        parsed = await self._parseObject(app, a_fields, AADAPP_NODE_LABEL)
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
        sp_fields = [
            "appDisplayName",
            "objectId",
            "appId",
            "accountEnabled",
            "servicePrincipalNames",
            "homepage",
            "passwordCredentials",
            "keyCredentials",
            "appOwnerTenantId",
            "publisherName",
            "microsoftFirstParty",
        ]

        parsed = await self._parseObject(spn, sp_fields, AADSPN_NODE_LABEL)
        parsed["passwordCredentialCount"] = len(spn.get("passwordCredentials", 0))
        parsed["keyCredentialCount"] = len(spn.get("keyCredentials", 0))
        post_spn = await self._postProcessResource(parsed)
        self.neo.insert_asset(
            post_spn, AADOBJECT_NODE_LABEL, post_spn["objectId"], [AADSPN_NODE_LABEL]
        )
        for owner in spn["owners"]:
            self.neo.create_relationship(
                owner, AADOBJECT_NODE_LABEL, spn["objectId"], AADSPN_NODE_LABEL, OWNER
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

    async def _process_json(self, json):
        res = orjson.loads(json)

        if res.get("id") and res.get("id").startswith("/tenants"):
            await self._processTenant(res)

        # AAD OBJECTS
        elif objtype := res.get("objectType"):
            await self._aad_methods[objtype](res)

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

        # TODO: Pass whole neo4j params from frontend or use .env
        self.neo = Neo4j(user=neo_user, password=neo_pass)
        if zipfile.is_zipfile(upload):
            self.status = f"Unzipping {filename}"
            tempdir = mkdtemp()
            zipfile.ZipFile(upload).extractall(tempdir)
            sqlite_files = [
                f for f in Path(tempdir).glob("*") if await self.is_sqlite(f)
            ]
            await asyncio.gather(*[self.process_sqlite(s) for s in sqlite_files])

            shutil.rmtree(tempdir)
