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

from . import OUTPUT_FOLDER, SSL_CONTEXT
from .aad import rbac_backfill
from .auth import Context
from .utils import sqlite_writer


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
            api_versions = (
                re.search(
                    "The supported api-versions are '(.*?)'. The supported locations",
                    ex.message,
                )
                .groups()[0]
                .split(", ")
            )
            api_versions = list(
                filter(lambda v: v not in invalid_versions, api_versions)
            )
            if api_versions:
                return await _query_resource(
                    client,
                    resource_id,
                    api_version=api_versions[-1],
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

        # GET RESOURCES IN SUBSCRIPTION
        async for resource in rm_client.resources.list():
            res = await _query_resource(rm_client, resource.id)
            if res:
                output = OUTPUT_FOLDER / f"{sub.subscription_id}.sqlite"
                await sqlite_writer(output, res)
            else:
                logger.warning(f"Could not access - {resource}")

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
            role_dict["roleName"] = definition.role_name
            role_dict["roleType"] = definition.role_type
            role_dict["roleDescription"] = definition.description
            roles.append(role_dict)
        except Exception as ex:
            logger.error(ex)
    logger.info(f"Finishing rbac permissions for subscription: {sub.subscription_id}")
    return roles


@logger.catch()
async def _query_management_certs(ctx: Context, sub: Subscription):
    logger.info(f"Enumerating management certs for subscription: {sub.subscription_id}")
    headers = {"x-ms-version": "2012-03-01"}

    certs = []
    async with aiohttp.ClientSession(headers=headers, connector=SSL_CONTEXT) as session:
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
    logger.info(f"Finished management certs for subscription: {sub.subscription_id}")
    return certs


@logger.catch()
async def query_arm(ctx: Context, args: argparse.Namespace) -> None:
    logger.info(f"Starting enumeration for ARM - {ctx.cloud['ARM']}")

    async with SubscriptionClient(
        ctx.cred_async, base_url=ctx.cloud["ARM"]
    ) as sub_client:
        async for tenant in sub_client.tenants.list():
            tenant_dict = tenant.as_dict()
            tenant_dict["subscriptions"] = []
            logger.info(
                f"Enumerating subscription and resource groups for tenant {tenant.tenant_id}"
            )

            # GET LIST OF SUBS.
            sub_list = []
            async for subscription in sub_client.subscriptions.list():
                if args.subs:
                    if not subscription.subscription_id in args.subs:
                        continue
                if args.nosubs:
                    if subscription.subscription_id in args.nosubs:
                        continue
                sub_list.append(subscription)

            if not sub_list:
                logger.error(f"No subscriptions found for {tenant.tenant_id}")
                continue

            # ENUMERATE MANAGEMENT CERTS
            if ctx.cloud["MGMT"]:
                certsTasks = [
                    asyncio.create_task(_query_management_certs(ctx, sub))
                    for sub in sub_list
                ]

                certs_output = OUTPUT_FOLDER / f"certs.sqlite"

                for cert in asyncio.as_completed(*[certsTasks]):
                    if await cert:
                        await sqlite_writer(certs_output, cert)

            # ENUMERATE RBAC
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(sub_list))
            rbacTasks = {executor.submit(_query_rbac, ctx, sub) for sub in sub_list}

            backfills = {
                "User": set(),
                "Group": set(),
                "ServicePrincipal": set(),
                "Application": set(),
            }  # Dict of object IDs to hold for AAD enumeration

            rbac_output = OUTPUT_FOLDER / f"rbac.sqlite"
            for rbac in concurrent.futures.as_completed(*[rbacTasks]):
                if rbac.result():
                    for role in rbac.result():
                        await sqlite_writer(rbac_output, role)
                        if args.backfill:
                            backfills[role["principal_type"]].add(role["principal_id"])

            # Only do backfill if azure argument is true (meaning specified on command line)
            if args.azure and args.backfill:
                await rbac_backfill(ctx, args, backfills)

            # ENUMERATE TENANT DATA
            subTasks = [
                asyncio.create_task(_query_subscription(ctx, sub)) for sub in sub_list
            ]

            for result in asyncio.as_completed(*[subTasks]):
                tenant_dict["subscriptions"].append(await result)

            tenant_output = OUTPUT_FOLDER / f"tenant.sqlite"
            await sqlite_writer(tenant_output, tenant_dict)
