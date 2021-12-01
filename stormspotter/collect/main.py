import asyncio
import logging
import shutil
import time
from tarfile import TarFile
from typing import Any, List

import click
import typer
from azure.identity.aio import AzureCliCredential, VisualStudioCodeCredential
from rich import print
from rich.logging import RichHandler

from .aad import query_aad
from .arm import query_arm
from .context import CollectorContext
from .enums import Cloud, EnumMode
from .utils import gen_results_tables

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    help="Collection commands",
)

log = logging.getLogger("rich")


async def start_collect(ctx: CollectorContext):

    # Create the directory for output
    ctx.output_dir.mkdir(parents=True)

    # Create and run tasks for AAD and/or ARM
    tasks = []

    if ctx.mode in [EnumMode.AAD, EnumMode.BOTH]:
        tasks.append(asyncio.create_task(query_aad(ctx)))

    if ctx.mode in [EnumMode.ARM, EnumMode.BOTH]:
        tasks.append(asyncio.create_task(query_arm(ctx)))

    await asyncio.wait(tasks)

    # Ensure credential object gets closed properly
    await ctx.cred.close()


@click.pass_context
def _begin_run(ctx: typer.Context, result: Any):
    """Invoke async run of collector"""

    collector_ctx: CollectorContext = ctx.obj["ctx"]
    if collector_ctx.cred:
        start_time = time.time()
        asyncio.run(start_collect(collector_ctx))

        log.info(f"--- COMPLETION TIME: {time.time() - start_time} seconds\n")

        # Create results tar file
        with TarFile.open(f"{collector_ctx.output_dir}.tar.xz", mode="w:xz") as tf:
            tf.add(collector_ctx.output_dir)
        shutil.rmtree(collector_ctx.output_dir)

        log.info(f"--- Results saved to {collector_ctx.output_dir}.tar.xz ---")
        print(
            gen_results_tables(collector_ctx._aad_results, collector_ctx._arm_results),
        )


@app.callback(result_callback=_begin_run)
def main(ctx: typer.Context):
    """
    Stormspotter Collector CLI.
    """
    ctx.ensure_object(dict)


@app.command()
def azcli(
    ctx: typer.Context,
    cloud: Cloud = typer.Option(
        Cloud.PUBLIC, "--cloud", help="Cloud environment", metavar=""
    ),
    mode: EnumMode = typer.Option(
        EnumMode.BOTH,
        "--mode",
        help="AAD, ARM, or both",
        metavar="",
        case_sensitive=False,
    ),
    backfill: bool = typer.Option(
        False,
        "--backfill",
        help="Perform AAD enumeration only for ARM RBAC object IDs",
        metavar="",
    ),
    include_sub: List[str] = typer.Option(
        [], "--include-subs", "-is", help="Only scan specific subscriptions", metavar=""
    ),
    exclude_sub: List[str] = typer.Option(
        [], "--exclude-subs", "-es", help="Exclude specific subscriptions", metavar=""
    ),
):
    """Authenticate and run with Azure CLI credentials"""
    log.info("Attempting to login with Azure CLI credentials...")
    cred = AzureCliCredential()

    ctx.obj["ctx"] = CollectorContext(
        cred,
        cloud._cloud,
        mode,
        backfill,
        include_sub,
        exclude_sub,
    )


@app.command()
def vscode(
    ctx: typer.Context,
    tenant_id: str = typer.Option("", "--tenant", "-t", help="Tenant ID", metavar=""),
    cloud: Cloud = typer.Option(
        Cloud.PUBLIC, "--cloud", help="Cloud environment", metavar=""
    ),
    mode: EnumMode = typer.Option(
        EnumMode.BOTH,
        "--mode",
        help="AAD, ARM, or both",
        metavar="",
        case_sensitive=False,
    ),
    backfill: bool = typer.Option(
        False,
        "--backfill",
        help="Perform AAD enumeration only for ARM RBAC object IDs",
        metavar="",
    ),
    include_sub: List[str] = typer.Option(
        [], "--include-subs", "-is", help="Only scan specific subscriptions", metavar=""
    ),
    exclude_sub: List[str] = typer.Option(
        [], "--exclude-subs", "-es", help="Exclude specific subscriptions", metavar=""
    ),
):
    """Authenticate and run with VS Code credentials"""
    log.info("Attempting to login with VS Code credentials...")
    cred = VisualStudioCodeCredential(tenant_id=tenant_id)

    ctx.obj["ctx"] = CollectorContext(
        cred,
        cloud._cloud,
        mode,
        backfill,
        include_sub,
        exclude_sub,
        tenant_id=tenant_id,
    )
