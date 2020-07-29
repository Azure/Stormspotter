import argparse
import asyncio
from loguru import logger

from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from stormcollector.auth import Context


async def query_arm(ctx: Context, args: argparse.Namespace):
    logger.info(f"Starting enumeration for ARM - {ctx.cloud['ARM']}")

    with SubscriptionClient(ctx.cred, base_url=ctx.cloud["ARM"]) as sub_client:
        tenants = [tenant async for tenant in sub_client.tenants.list()]
        print(tenants)
