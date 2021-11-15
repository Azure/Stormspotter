import asyncio
import logging
import xml

import aiohttp
import orjson
from azure.mgmt.authorization.aio import AuthorizationManagementClient
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from azure.mgmt.resource.subscriptions.models import Subscription

from stormspotter.collect.enums import EnumMode

from .aad import rbac_backfill
from .context import CollectorContext
from .utils import sqlite_writer

log = logging.getLogger("rich")


async def _query_rbac(ctx: CollectorContext, sub: Subscription):
    """Query RBAC permissions on a subscription and resources below it"""

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
        log.info(f"Finishing rbac permissions for subscription: {sub.subscription_id}")
        return roles


async def _query_management_certs(ctx: CollectorContext, sub: Subscription):
    """Checks for management certs on subscriptions"""

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
        f"Finished management certs enumeration for subscription: {sub.subscription_id}"
    )
    return certs


async def query_arm(ctx: CollectorContext) -> None:
    """Starts enumeration for Azure Resource Manager"""

    ARM_URL = ctx.cloud.endpoints.resource_manager

    log.info(f"Starting enumeration for ARM - {ARM_URL}")

    async with SubscriptionClient(ctx.cred, base_url=ARM_URL) as sub_client:

        # Go through available tenants
        async for tenant in sub_client.tenants.list():
            log.info(
                f"Enumerating subscription and resource groups for tenant {tenant.tenant_id}"
            )
            await sqlite_writer(ctx.output_dir / "tenant.sqlite", tenant.as_dict())

            # Get list of subscriptions
            # Check if include subs was passed. If so, only use those.
            # If exclude_subs is also passed, do not add if in passed list
            sub_list = []
            async for subscription in sub_client.subscriptions.list():
                if ctx.include_subs:
                    if not subscription.subscription_id in ctx.include_subs:
                        continue

                if ctx.exclude_subs:
                    if subscription.subscription_id in ctx.exclude_subs:
                        continue

                sub_list.append(subscription)
                await sqlite_writer(
                    ctx.output_dir / "subscriptions.sqlite",
                    orjson.dumps(sub_list, default=lambda x: x.as_dict()).decode(),
                )

            if not sub_list:
                log.error(f"No subscriptions found for {tenant.tenant_id}")
                continue

            # Check for management certs
            certsTasks = [
                asyncio.create_task(_query_management_certs(ctx, sub))
                for sub in sub_list
            ]
            certs_output = ctx.output_dir / f"management_certs.sqlite"

            for cert in asyncio.as_completed(*[certsTasks]):
                if await cert:
                    await sqlite_writer(certs_output, cert)

            # Enumerate RBAC
            rbac_output = ctx.output_dir / "rbac.sqlite"

            # Dict of object IDs to hold for AAD enumeration
            aad_backfills = {
                "User": set(),
                "Group": set(),
                "ServicePrincipal": set(),
                "Application": set(),
            }
            rbacTasks = [asyncio.create_task(_query_rbac(ctx, sub)) for sub in sub_list]
            for task in asyncio.as_completed(*[rbacTasks]):
                if roles := await task:
                    for role in roles:
                        await sqlite_writer(rbac_output, role)
                        if ctx.backfill:
                            aad_backfills[role["principal_type"]].add(
                                role["principal_id"]
                            )

            # We only need to backfill if only ARM and backfill are passed
            if ctx.mode == EnumMode.ARM and ctx.backfill:
                await rbac_backfill(ctx, aad_backfills)
