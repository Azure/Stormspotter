import argparse
import asyncio
import concurrent.futures
import re
import xml.dom.minidom

import aiohttp
from azure.core.exceptions import HttpResponseError
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.resource.resources.aio import ResourceManagementClient
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from azure.mgmt.resource.subscriptions.models import Subscription
from loguru import logger
from tinydb import TinyDB

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


async def _query_subscription(ctx: Context, sub: Subscription):

    logger.info(f"Querying for resources in subscription - {sub.subscription_id}")
    sub_dict = sub.as_dict()
    sub_dict["resourceGroups"] = []

    async with ResourceManagementClient(
        ctx.cred_async, sub.subscription_id, base_url=ctx.cloud["ARM"],
    ) as rm_client:

        # GET RESOURCE GROUPS
        async for r_group in rm_client.resource_groups.list():
            sub_dict["resourceGroups"].append(r_group.as_dict())

        db_path = OUTPUT_FOLDER / f"{sub.subscription_id}.json"
        db = TinyDB(db_path)

        # GET RESOURCES IN SUBSCRIPTION
        async for resource in rm_client.resources.list():
            resource = await _query_resource(rm_client, resource.id)
            db.insert(resource)
    logger.info(f"Finished querying - {sub.subscription_id}")
    return sub_dict


def _query_rbac(ctx: Context, sub: Subscription):
    logger.info(f"Enumerating rbac permissions for subscription: {sub.subscription_id}")
    auth_client = AuthorizationManagementClient(
        ctx.cred_msrest, sub.subscription_id, base_url=ctx.cloud["ARM"]
    )
    roles = []
    for role in auth_client.role_assignments.list():
        try:
            role_dict = role.as_dict()
            definition = auth_client.role_definitions.get_by_id(role.role_definition_id)
            role_dict["permissions"] = [p.as_dict() for p in definition.permissions]
            roles.append(role_dict)
        except Exception as ex:
            logger.error(ex)
    return roles


@logger.catch()
async def _query_management_certs(ctx: Context, sub: Subscription):
    logger.info(f"Enumerating management certs for subscription: {sub.subscription_id}")
    headers = {"x-ms-version": "2012-03-01"}

    certs = []
    async with aiohttp.ClientSession(headers=headers) as session:
        url = f"{ctx.cloud['MGMT']}/{sub.subscription_id}/certificates"
        async with session.get(url) as resp:
            if "ForbiddenError" in await resp.text():
                logger.warning(
                    f"Forbidden: Cannot enumerate management certs for {sub.subscription_id}"
                )
                return certs

            dom = xml.dom.minidom.parseString()
            for cert in dom.getElementsByTagName("SubscriptionCertificate"):
                cert_asset = {
                    "subscriptionId": sub.subscription_id,
                    "thumbprint": cert.getElementsByTagName(
                        "SubscriptionCertificateThumbprint"
                    )[0].firstChild.nodeValue,
                    "created": cert.getElementsByTagName("Created")[
                        0
                    ].firstChild.nodeValue,
                }
                certs.append(cert_asset)
    return certs


@logger.catch()
async def query_arm(ctx: Context, args: argparse.Namespace) -> None:
    logger.info(f"Starting enumeration for ARM - {ctx.cloud['ARM']}")

    sub_db_path = OUTPUT_FOLDER / f"subscriptions.json"
    sub_db = TinyDB(sub_db_path)

    rbac_db_path = OUTPUT_FOLDER / f"rbac.json"
    rbac_db = TinyDB(rbac_db_path)

    certs_db_path = OUTPUT_FOLDER / f"certs.json"
    certs_db = TinyDB(certs_db_path)

    async with SubscriptionClient(
        ctx.cred_async, base_url=ctx.cloud["ARM"]
    ) as sub_client:
        async for tenant in sub_client.tenants.list():
            tenant_dict = tenant.as_dict()
            tenant_dict["subscriptions"] = []
            logger.info(
                f"Enumerating subscription and resource groups for tenant {tenant.tenant_id}"
            )

            sub_list = []
            async for subscription in sub_client.subscriptions.list():
                if args.subs:
                    if not subscription.subscription_id in args.subs:
                        continue
                sub_list.append(subscription)

            subTasks = [
                asyncio.create_task(_query_subscription(ctx, sub)) for sub in sub_list
            ]

            if ctx.cloud["MGMT"]:
                certsTasks = [
                    asyncio.create_task(_query_management_certs(ctx, sub))
                    for sub in sub_list
                ]
                for cert in asyncio.as_completed(*[certsTasks]):
                    if res := await cert:
                        certs_db.insert(res)

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(sub_list))
            rbacTasks = {executor.submit(_query_rbac, ctx, sub) for sub in sub_list}

            for result in asyncio.as_completed(*[subTasks]):
                tenant_dict["subscriptions"].append(await result)

            sub_db.insert(tenant_dict)

            for rbac in concurrent.futures.as_completed(rbacTasks):
                try:
                    rbac_db.insert_multiple(rbac.result())
                except Exception as e:
                    logger.error(e)
