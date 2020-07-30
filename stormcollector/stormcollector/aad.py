import argparse
import asyncio
from dataclasses import dataclass

import aiohttp
from loguru import logger
from tinydb import TinyDB

from . import OUTPUT_FOLDER
from .auth import Context

TinyDB.DEFAULT_TABLE_KWARGS = {"cache_size": 0}


@dataclass
class AADObject:
    resource = str
    ctx: Context
    tenant_id: str
    base_url: str
    api_version: str = "api-version=1.6-internal"

    async def parse(self, value):
        return value

    async def expand(self, resource_id, prop):
        user_url = f"{self.base_url}/{self.tenant_id}/{self.resource}/{resource_id}/{prop}?{self.api_version}"
        async with self.session.get(user_url) as expanded:
            return await expanded.json()

    @logger.catch()
    async def query_objects(self, headers: dict):
        logger.info(f"Starting query for {self.__class__.__name__}")

        db_path = OUTPUT_FOLDER / f"{self.__class__.__name__}.json"
        db = TinyDB(db_path)

        self.session = aiohttp.ClientSession(headers=headers)
        user_url = (
            f"{self.base_url}/{self.tenant_id}/{self.resource}?{self.api_version}"
        )

        next_link = True
        while next_link:
            async with self.session.get(user_url) as resp:
                response = await resp.json()
                if "odata.error" in response:
                    raise Exception(response)

                for value in response["value"]:
                    parsedVal = await self.parse(value)
                    db.insert(parsedVal)
                if "odata.nextLink" in response:
                    user_url = f"{self.base_url}/{self.tenant_id}/{response['odata.nextLink']}&{self.api_version}"
                else:
                    next_link = False
        await self.session.close()
        logger.info(f"Finished query for {self.__class__.__name__}")


@dataclass
class AADUser(AADObject):
    resource: str = "users"


@dataclass
class AADServicePrincipal(AADObject):
    resource = "servicePrincipals"

    async def parse(self, value):

        if not value.get("microsoftFirstParty"):
            owners = await self.expand(
                value.get("objectId") or value.get("id"), "owners"
            )
            owner_ids = [
                owner.get("objectId") or owner.get("id") for owner in owners["value"]
            ]

            value["owners"] = owner_ids
        else:
            value["owners"] = []
        return value


@dataclass
class AADApplication(AADObject):
    resource = "applications"

    async def parse(self, value):
        owners = await self.expand(value.get("objectId") or value.get("id"), "owners")
        owner_ids = [
            owner.get("objectId") or owner.get("id") for owner in owners["value"]
        ]

        value["owners"] = owner_ids
        return value


@dataclass
class AADGroup(AADObject):
    resource: str = "groups"

    async def parse(self, value):
        members = await self.expand(value.get("objectId") or value.get("id"), "members")
        member_ids = [
            member.get("objectId") or member.get("id") for member in members["value"]
        ]

        owners = await self.expand(value.get("objectId") or value.get("id"), "owners")
        owner_ids = [
            owner.get("objectId") or owner.get("id") for owner in owners["value"]
        ]

        value["members"] = member_ids
        value["owners"] = owner_ids
        return value


async def query_aad(ctx: Context, args: argparse.Namespace):
    logger.info(f"Checking access for Azure AD: {ctx.cloud['AAD']}")
    aad_types = AADObject.__subclasses__()
    # token = await ctx.cred.get_token(ctx.cloud["AAD"])
    token = await ctx.cred_async.get_token(f"{ctx.cloud['AAD']}/.default")
    headers = {"Authorization": f"Bearer {token.token}"}

    # Test for access to preferred AAD Graph. If fail, fallback to Microsoft Graph.
    session = aiohttp.ClientSession(headers=headers)
    user_url = f"{ctx.cloud['AAD']}/me?api-version=1.61-internal"
    tenantid = args.tenantid if hasattr(args, "tenantid") else "myorganization"

    async with session.get(user_url) as resp:
        response = await resp.json()

        # If odata.error is in response, it means AAD Graph was unsuccessful.
        if "odata.error" in response:
            logger.error(
                f"{ctx.cloud['AAD']} - {response['odata.error']['code']} - {response['odata.error']['message']['value']}"
            )

            # Test for access to MS Graph.
            logger.info(f"Checking access for Microsoft Graph: {ctx.cloud['GRAPH']}")
            token = await ctx.cred_async.get_token(f"{ctx.cloud['GRAPH']}/.default")
            headers = {"Authorization": f"Bearer {token.token}"}
            user_url = f"{ctx.cloud['GRAPH']}/beta/me"

            async with session.get(user_url, headers=headers) as graph_req:
                graph_resp = await graph_req.json()

                # If "error" in response, no access to MS Graph. Abort AAD enumeration.
                if "error" in graph_resp:
                    logger.error(
                        f"{ctx.cloud['GRAPH']} - {graph_resp['error']['code']} - {graph_resp['error']['message']}"
                    )
                    return await session.close()

            await asyncio.gather(
                *[
                    aad_type(
                        ctx=ctx,
                        tenant_id="beta",
                        base_url=ctx.cloud["GRAPH"],
                        api_version="",
                    ).query_objects(headers)
                    for aad_type in aad_types
                ]
            )
        else:
            logger.info(f"Starting enumeration for Azure AD: {ctx.cloud['AAD']}")
            await asyncio.gather(
                *[
                    aad_type(
                        ctx=ctx, tenant_id=tenantid, base_url=ctx.cloud["AAD"],
                    ).query_objects(headers)
                    for aad_type in aad_types
                ]
            )
    await session.close()
