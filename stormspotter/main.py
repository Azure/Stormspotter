import asyncio
import logging
from pathlib import Path
from tarfile import TarFile, is_tarfile
from typing import Optional

import typer
import uvicorn
from aiocypher import Config
from aiocypher.aioneo4j.driver import Driver
from rich import inspect, print
from rich.logging import RichHandler

from .collect import main as collect_main
from .ingest.ingestion import start_parsing

app = typer.Typer(
    name="Stormspotter CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

# Adding subcommand apps
app.add_typer(collect_main.app, name="collect")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose/Debug output"),
):
    """
    Stormspotter Collector CLI.
    """
    ctx.ensure_object(dict)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )


@app.command(help="Ingest results into neo4j")
def ingest(
    file: Path = typer.Option(
        ...,
        "-f",
        help="Stormspotter collection file",
        metavar="",
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    user: str = typer.Option("neo4j", "--user", help="Neo4j Username", metavar=""),
    passwd: str = typer.Option("password", "--pass", help="Neo4j Password", metavar=""),
    server: str = typer.Option(
        "bolt://127.0.0.1", "--server", help="Neo4j Server", metavar=""
    ),
    port: int = typer.Option(7687, "--port", help="Neo4j port", metavar=""),
):
    if not is_tarfile(file):
        raise Exception(f"{file} is not a tar file!")

    # Extract tar file and get directory name
    with TarFile.open(file, mode="r:xz") as tf:
        results_dir = Path(tf.getnames()[0])
        tf.extractall("")

    sqlite_files = list(results_dir.glob("*.sqlite"))
    neo4j_driver = Driver(Config(f"{server}:{port}", user, passwd))
    asyncio.run(start_parsing(sqlite_files, neo4j_driver), debug=True)


@app.command(help="Start Stormspotter server")
def server(
    host: str = typer.Argument("127.0.0.1", help="Host address to listen on"),
    port: int = typer.Argument(9090, help="Host port to listen on"),
    reload: bool = typer.Option(
        False, "--reload", help="Reload server on file change (dev mode)"
    ),
):
    uvicorn.run(
        "stormspotter.server.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_includes=["*.py", "*.html", "*.js"],
        log_level=logging.root.level,
        use_colors=True,
        log_config=None,
    )
