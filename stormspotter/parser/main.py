import asyncio
import logging
import time
from typing import Any, List

import typer
from rich import print


app = typer.Typer(
    name="Stormspotter Parser CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

log = logging.getLogger("rich")


@app.command()
def main():
    pass
