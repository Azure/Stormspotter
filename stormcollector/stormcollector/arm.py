import argparse
import re
from loguru import logger
from tinydb import TinyDB

from azure.core.exceptions import HttpResponseError
from azure.mgmt.resource.resources.aio import ResourceManagementClient
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from stormcollector.auth import Context

from . import OUTPUT_FOLDER


async def _query_resource(
    client: ResourceManagementClient,
    resource_id: str,
    api_version: str = "2018-02-14",
    invalid_versions: list = [],
):
    try:
        response = await client.resources.get_by_id(resource_id, api_version)
        return response.as_dict()
    except HttpResponseError as ex:
        if "No registered resource provider found for location" in ex.message:
            invalid_versions.append(api_version)
            api_versions = re.search(
                "The supported api-versions are '(.*?),", ex.message
            ).groups()
            api_versions = list(
                filter(lambda v: v not in invalid_versions, api_versions)
            )
            if api_versions:
                return await _query_resource(
                    client,
                    resource_id,
                    api_version=api_versions[0],
                    invalid_versions=invalid_versions,
                )


@logger.catch()
async def query_arm(ctx: Context, args: argparse.Namespace) -> None:
    logger.info(f"Starting enumeration for ARM - {ctx.cloud['ARM']}")

    try:
        async with SubscriptionClient(
            ctx.cred, base_url=ctx.cloud["ARM"]
        ) as sub_client:
            async for tenant in sub_client.tenants.list():
                tenant_dict = tenant.as_dict()
                tenant_dict["subscriptions"] = []
                logger.info(
                    f"Enumerating subscription and resource groups for tenant {tenant.tenant_id}"
                )

                async for subscription in sub_client.subscriptions.list():
                    if args.subs:
                        if not subscription.subscription_id in args.subs:
                            continue

                    logger.info(
                        f"Querying for resources in subscription - {subscription.subscription_id}"
                    )
                    sub_dict = subscription.as_dict()
                    sub_dict["resourceGroups"] = []

                    async with ResourceManagementClient(
                        ctx.cred,
                        subscription.subscription_id,
                        base_url=ctx.cloud["ARM"],
                    ) as rm_client:

                        # GET RESOURCE GROUPS
                        async for r_group in rm_client.resource_groups.list():
                            sub_dict["resourceGroups"].append(r_group.as_dict())

                        # GET RESOURCES IN SUBSCRIPTION
                        async for resource in rm_client.resources.list():
                            resource = await _query_resource(rm_client, resource.id)

                    tenant_dict["subscriptions"].append(sub_dict)

                db_path = OUTPUT_FOLDER / f"subscriptions.json"
                db = TinyDB(db_path)
                db.insert(tenant_dict)
    except Exception as e:
        logger.error(e)
