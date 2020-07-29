import argparse
import asyncio
import aiohttp
from dataclasses import dataclass
from loguru import logger
from tinydb import TinyDB

from .auth import Context
from . import OUTPUT_FOLDER

TinyDB.DEFAULT_TABLE_KWARGS = {"cache_size": 0}


@dataclass
class AADObject:
    resource = str
    api_version: str = "1.61-internal"
    ctx: Context = None
    tenant_id: str = None

    async def parse(self, value):
        return value

    async def expand(self, resource_id, prop):
        base_url = self.ctx.cloud["AAD"]

        user_url = f"{base_url}/{self.tenant_id}/{self.resource}/{resource_id}/{prop}?api-version={self.api_version}"
        async with self.session.get(user_url) as expanded:
            return await expanded.json()

    async def query_resources(self, headers: dict):
        logger.info(f"Starting query for {self.__class__.__name__}")

        db_path = OUTPUT_FOLDER / f"{self.__class__.__name__}.json"
        db = TinyDB(db_path)

        self.session = aiohttp.ClientSession(headers=headers)

        base_url = self.ctx.cloud["AAD"]
        user_url = f"{base_url}/{self.tenant_id}/{self.resource}?api-version={self.api_version}"

        next_link = True
        while next_link:
            async with self.session.get(user_url) as resp:
                response = await resp.json()
                for value in response["value"]:
                    parsedVal = await self.parse(value)
                    db.insert(parsedVal)
                if "odata.nextLink" in response:
                    user_url = f"{base_url}/{self.tenant_id}/{response['odata.nextLink']}&api-version={self.api_version}"
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
        if not value["microsoftFirstParty"]:
            owners = await self.expand(value["objectId"], "owners")
            owner_ids = [owner["objectId"] for owner in owners["value"]]

            value["owners"] = owner_ids
        else:
            value["owners"] = []
        return value


@dataclass
class AADApplication(AADObject):
    resource = "applications"

    async def parse(self, value):
        owners = await self.expand(value["objectId"], "owners")
        owner_ids = [owner["objectId"] for owner in owners["value"]]

        value["owners"] = owner_ids
        return value


@dataclass
class AADGroup(AADObject):
    resource: str = "groups"

    async def parse(self, value):
        members = await self.expand(value["objectId"], "members")
        member_ids = [member["objectId"] for member in members["value"]]

        owners = await self.expand(value["objectId"], "owners")
        owner_ids = [owner["objectId"] for owner in owners["value"]]

        value["members"] = member_ids
        value["owners"] = owner_ids
        return value


@logger.catch()
async def query_aad(ctx: Context, args: argparse.Namespace):
    logger.info(f"Starting enumeration for Azure AD: {ctx.cloud['AAD']}")
    aad_types = AADObject.__subclasses__()
    token = await ctx.cred.get_token(ctx.cloud["AAD"])
    headers = {"Authorization": f"Bearer {token.token}"}

    await asyncio.gather(
        *[
            aad_type(ctx=ctx, tenant_id=args.tenantid).query_resources(headers)
            for aad_type in aad_types
        ]
    )
