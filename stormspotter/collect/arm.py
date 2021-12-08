import asyncio
import logging
import time
import xml

import aiohttp
from azure.mgmt.authorization.aio import AuthorizationManagementClient
from azure.mgmt.resource.resources.aio import ResourceManagementClient
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from azure.mgmt.resource.subscriptions.models import Subscription
from rich import print, print_json

from stormspotter.collect.enums import EnumMode

from .aad import query_aad
from .context import CollectorContext
from .utils import sqlite_writer

log = logging.getLogger("rich")


async def _query_rbac(ctx: CollectorContext, sub: Subscription):
    """Query RBAC permissions on a subscription and resources below it"""
    start_time = time.time()

    log.info(f"Enumerating RBAC permissions for subscription: {sub.subscription_id}")

    # The most recent stable version is v2015 but we can move up
    async with AuthorizationManagementClient(
        ctx.cred,
        sub.subscription_id,
        api_version="2018-01-01-preview",
        base_url=ctx.cloud.endpoints.resource_manager,
    ) as auth_client:

        roles = []
        async for role in auth_client.role_assignments.list():
            try:
                role_dict = role.as_dict()
                definition = await auth_client.role_definitions.get_by_id(
                    role.role_definition_id
                )
                role_dict["permissions"] = [p.as_dict() for p in definition.permissions]
                role_dict["roleName"] = definition.role_name
                role_dict["roleType"] = definition.role_type
                role_dict["roleDescription"] = definition.description
                roles.append(role_dict)
            except Exception as ex:
                log.error(ex)
        log.info(
            f"Finishing rbac permissions for subscription: {sub.subscription_id} ({time.time() - start_time} sec)"
        )
        return roles


async def _query_management_certs(ctx: CollectorContext, sub: Subscription):
    """Checks for management certs on subscriptions"""
    start_time = time.time()

    log.info(f"Enumerating management certs for subscription: {sub.subscription_id}")
    headers = {"x-ms-version": "2012-03-01"}

    certs = []
    async with aiohttp.ClientSession(headers=headers) as session:
        url = f"{ctx.cloud.endpoints.management}{sub.subscription_id}/certificates"
        async with session.get(url) as resp:
            if "ForbiddenError" in await resp.text():
                log.warning(
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
                ctx._arm_results.update(["ManagementCerts"])

            log.info(
                f"[bold green] Found management certs for {sub.subscription_id}![/]"
            )

    log.info(
        f"Finished management certs enumeration for subscription: {sub.subscription_id} ({time.time() - start_time} sec)"
    )
    return certs


async def _query_subscription(ctx: CollectorContext, sub: Subscription):
    """Query a subscription and its resources"""
    start_time = time.time()

    log.info(f"Querying for resources in subscription - {sub.subscription_id}")
    async with ResourceManagementClient(
        ctx.cred,
        sub.subscription_id,
        base_url=ctx.cloud.endpoints.resource_manager,
    ) as resourcemgr_client:

        # Get providers for the subscription.
        # This makes it easier to query a resource by the correct API version
        provider_dict = {}
        async for provider in resourcemgr_client.providers.list():
            for rtype in provider.resource_types:
                name_and_type = (
                    f"{provider.namespace.lower()}/{rtype.resource_type.lower()}"
                )
                if rtype.api_versions:
                    provider_dict[name_and_type] = (
                        rtype.default_api_version or rtype.api_versions[0]
                    )

        # Get the resources!
        output = ctx.output_dir / f"{sub.subscription_id}.sqlite"

        # First the resource groups
        async for resource_group in resourcemgr_client.resource_groups.list():
            await sqlite_writer(output, resource_group.as_dict())
            ctx._arm_results.update([resource_group.type])

        # Then the resources
        async for resource in resourcemgr_client.resources.list():
            api_version = provider_dict.get(resource.type.lower())

            if res := await resourcemgr_client.resources.get_by_id(
                resource.id, api_version
            ):
                await sqlite_writer(output, res.as_dict())
                ctx._arm_results.update([res.type])
            else:
                log.warning(f"Could not access - {resource}")

    log.info(
        f"Finished querying subscription - {sub.subscription_id} ({time.time() - start_time} sec)"
    )


async def _start_query(ctx: CollectorContext, subscription: Subscription):
    """Starts all queries on a subscription"""
    if ctx.include_subs:
        if not subscription.subscription_id in ctx.include_subs:
            return

    if ctx.exclude_subs:
        if subscription.subscription_id in ctx.exclude_subs:
            return

    await sqlite_writer(
        ctx.output_dir / "subscription.sqlite",
        subscription.as_dict(),
    )

    # Check for management certs
    if certs := await _query_management_certs(ctx, subscription):
        certs_output = ctx.output_dir / f"management_certs.sqlite"
        await sqlite_writer(certs_output, certs)

    # Enumerate RBAC
    rbac_output = ctx.output_dir / "rbac.sqlite"
    object_ids = set()
    if roles := await _query_rbac(ctx, subscription):
        for role in roles:
            await sqlite_writer(rbac_output, role)
            if ctx.backfill:
                object_ids.add(role["principal_id"])

    # We only need to backfill if only ARM and backfill are passed
    if ctx.mode == EnumMode.BACKFILL and object_ids:
        log.info(f"Performing ARM RBAC backfill enumeration for {subscription.id}")
        start_time = time.time()
        await query_aad(ctx, list(object_ids))
        log.info(
            f"Completed ARM RBAC backfill enumeration ({time.time() - start_time} sec)"
        )

    # Enumerate subscription
    await _query_subscription(ctx, subscription)


async def query_arm(ctx: CollectorContext) -> None:
    """Starts enumeration for Azure Resource Manager"""

    ARM_URL = ctx.cloud.endpoints.resource_manager

    log.info(f"Starting enumeration for ARM - {ARM_URL}")

    async with SubscriptionClient(ctx.cred, base_url=ARM_URL) as sub_client:

        # Go through available tenants
        async for tenant in sub_client.tenants.list():
            log.info(f"Found tenant {tenant.tenant_id}")
            await sqlite_writer(ctx.output_dir / "tenant.sqlite", tenant.as_dict())

        # Get list of subscriptions
        # Check if include subs was passed. If so, only use those.
        # If exclude_subs is also passed, do not add if in passed list
        # Finally, if sub in not wanted tenants, then move on
        sub_list = []

        await asyncio.gather(
            *[_start_query(ctx, sub) async for sub in sub_client.subscriptions.list()]
        )
