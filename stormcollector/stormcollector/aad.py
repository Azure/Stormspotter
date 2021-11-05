import argparse
import asyncio
import time
from dataclasses import dataclass
from itertools import chain

import aiohttp
from loguru import logger

from . import OUTPUT_FOLDER, SSL_CONTEXT
from .auth import Context
from .utils import sqlite_writer


class _TokenEvent(asyncio.Event):
    """Handles manual refreshing of access tokens during AAD enumeration"""

    def __init__(self, ctx: Context, base_url: str, objName: str) -> None:
        super().__init__()
        self.currentToken = None
        self.token_refresh_task = asyncio.create_task(
            self._get_new_token_for_aad_enum(ctx, base_url, objName)
        )

    async def _get_new_token_for_aad_enum(
        self, ctx: Context, base_url: str, objName: str
    ):
        """Background task to get new token before access token expiration."""
        while True:
            self.currentToken = await ctx.cred_async.get_token(base_url + "/.default")

            # Set event to resume enumeration
            self.set()

            # Stop enumeration 15 seconds before token set to expire
            now = int(time.time())
            await asyncio.sleep(self.currentToken.expires_on - now - 15)

            # Prevent requests by clearing event
            self.clear()
            logger.info(f"Waiting for new access tokens for {objName} enumeration...")

            # Check to see if expiration has passed yet. Refresh after expiration to be safe.
            scope = base_url + "/.default"
            self.currentToken = await ctx.cred_async.get_token(scope)
            while self.currentToken.expires_on < int(time.time()):
                await asyncio.sleep(5)
                self.currentToken = await ctx.cred_async.get_token(scope)

            ctx.cred_sync, ctx.cred_async, ctx.cred_msrest = await Context.auth(
                ctx.args, ctx
            )
            logger.info(f"Resuming {objName} enumeration...")


@dataclass
class AADObject:
    resource = str
    ctx: Context
    tenant_id: str
    base_url: str
    api_version: str = "api-version=1.6-internal"

    def __post_init__(self):
        self._token_event = _TokenEvent(
            self.ctx, self.base_url, self.__class__.__name__
        )

    async def parse(self, value):
        return value

    async def expand(self, resource_id, prop):
        user_url = f"{self.base_url}/{self.tenant_id}/{self.resource}/{resource_id}/{prop}?{self.api_version}"
        headers = {"Authorization": f"Bearer {self._token_event.currentToken.token}"}
        async with self.session.get(user_url, headers=headers) as expanded:
            return await expanded.json()

    @logger.catch()
    async def query_objects(self, object_id: str = None):

        # Prevent logging for each backfill item
        if not object_id:
            logger.info(f"Starting query for {self.__class__.__name__}")

        self.session = aiohttp.ClientSession(connector=SSL_CONTEXT)
        if object_id:
            user_url = f"{self.base_url}/{self.tenant_id}/{self.resource}/{object_id}?{self.api_version}"
        else:
            user_url = (
                f"{self.base_url}/{self.tenant_id}/{self.resource}?{self.api_version}"
            )

        next_link = True
        while next_link:

            await self._token_event.wait()
            headers = {
                "Authorization": f"Bearer {self._token_event.currentToken.token}"
            }

            async with self.session.get(user_url, headers=headers) as resp:
                response = await resp.json()
                if "odata.error" in response:
                    raise Exception(response)

                # If response contains value, it's normal enumeration.
                if response.get("value"):
                    for value in response["value"]:
                        parsedVal = await self.parse(value)
                        await sqlite_writer(
                            OUTPUT_FOLDER / f"{self.__class__.__name__}.sqlite",
                            parsedVal,
                        )
                    if "odata.nextLink" in response:
                        user_url = f"{self.base_url}/{self.tenant_id}/{response['odata.nextLink']}&{self.api_version}"
                    else:
                        next_link = False
                # Else it's backfill
                else:
                    parsedVal = await self.parse(response)
                    await sqlite_writer(
                        OUTPUT_FOLDER / f"{self.__class__.__name__}.sqlite", parsedVal,
                    )
                    next_link = False

        # Finish cleanly
        await self.session.close()
        self._token_event.token_refresh_task.cancel()

        # Prevent logging for each backfill item
        if not object_id:
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
class AADRole(AADObject):
    resource = "directoryRoles"

    async def parse(self, value):
        members = await self.expand(value.get("objectId"), "members")
        member_ids = [
            member.get("objectId") or member.get("id") for member in members["value"]
        ]
        value["members"] = member_ids

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


async def query_aad(ctx: Context, args: argparse.Namespace, backfills: dict = None):
    logger.info(f"Checking access for Azure AD: {ctx.cloud['AAD']}")
    aad_types = AADObject.__subclasses__()

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
            user_url = f"{ctx.cloud['GRAPH']}/beta/users"

            async with session.get(user_url, headers=headers) as graph_req:
                graph_resp = await graph_req.json()

                # If "error" in response, no access to MS Graph. Abort AAD enumeration.
                if "error" in graph_resp:
                    logger.error(
                        f"{ctx.cloud['GRAPH']} - {graph_resp['error']['code']} - {graph_resp['error']['message']}"
                    )
                    return await session.close()

            if backfills:
                await asyncio.gather(
                    list(
                        chain(
                            [
                                AADUser(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["User"]
                            ],
                            [
                                AADGroup(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["Group"]
                            ],
                            [
                                AADServicePrincipal(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["ServicePrincipal"]
                            ],
                        )
                    )
                )
            else:
                await asyncio.gather(
                    *[
                        aad_type(
                            ctx=ctx,
                            tenant_id="beta",
                            base_url=ctx.cloud["GRAPH"],
                            api_version="",
                        ).query_objects()
                        for aad_type in aad_types
                    ]
                )
        else:
            logger.info(f"Starting enumeration for Azure AD: {ctx.cloud['AAD']}")

            if backfills:
                await asyncio.gather(
                    *list(
                        chain(
                            [
                                AADUser(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["User"]
                            ],
                            [
                                AADGroup(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["Group"]
                            ],
                            [
                                AADServicePrincipal(
                                    ctx=ctx,
                                    tenant_id="beta",
                                    base_url=ctx.cloud["GRAPH"],
                                    api_version="",
                                ).query_objects(obj)
                                for obj in backfills["ServicePrincipal"]
                            ],
                        )
                    )
                )
            else:
                await asyncio.gather(
                    *[
                        aad_type(
                            ctx=ctx, tenant_id=tenantid, base_url=ctx.cloud["AAD"],
                        ).query_objects()
                        for aad_type in aad_types
                    ]
                )
    await session.close()


async def rbac_backfill(ctx: Context, args: argparse.Namespace, backfills: dict):
    logger.info("Performing AAD backfill enumeration")
    await query_aad(ctx, args, backfills)
    logger.info("Completed AAD backfill enumeration")
