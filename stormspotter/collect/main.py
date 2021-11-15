import asyncio
import logging
import time
from typing import Any, List

import click
import typer
from azure.identity.aio import AzureCliCredential

from stormspotter.collect.context import CollectorContext

from .enums import Cloud, EnumMode

app = typer.Typer(
    name="Stormspotter Collector CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

log = logging.getLogger("rich")


async def start_collect(ctx: CollectorContext):
    # ctx.output_dir.mkdir(parents=True)
    pass


@click.pass_context
def _begin_run(ctx: typer.Context, result: Any):
    """Invoke async run of collector"""

    collector_ctx: CollectorContext = ctx.obj["ctx"]
    if collector_ctx.cred:
        start_time = time.time()
        asyncio.run(start_collect(collector_ctx))
        log.info(f"--- COMPLETION TIME: {time.time() - start_time} seconds")


@app.callback(result_callback=_begin_run)
def main(ctx: typer.Context):
    """
    Stormspotter Collector CLI.
    """
    ctx.ensure_object(dict)


@app.command()
def cli(
    ctx: typer.Context,
    cloud: Cloud = typer.Option(
        Cloud.PUBLIC, "--cloud", help="Cloud environment", metavar=""
    ),
    mode: EnumMode = typer.Option(
        EnumMode.BOTH, "--mode", help="AAD, ARM, or both", metavar=""
    ),
    backfill: bool = typer.Option(
        False,
        "--backfill",
        help="Perform AAD enumeration only for ARM RBAC object IDs",
        metavar="",
    ),
    include_subs: List[str] = typer.Option(
        [], "--include-subs", "-i", help="Only scan specific subscriptions", metavar=""
    ),
    exclude_subs: List[str] = typer.Option(
        [], "--exclude-subs", "-e", help="Exclude specific subscriptions", metavar=""
    ),
):
    """Authenticate and run with Azure CLI credentials"""
    log.info("Attempting to login with Azure CLI credentials...")
    cred = AzureCliCredential()

    ctx.obj["ctx"] = CollectorContext(
        cred, cloud, mode, backfill, include_subs, exclude_subs
    )
