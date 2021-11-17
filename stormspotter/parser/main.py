import logging
import typer
from rich import print

from .models import get_available_models

app = typer.Typer(
    name="Stormspotter Parser CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

log = logging.getLogger("rich")


@app.command()
def main(
    user: str = typer.Option("neo4j", "--user", help="Neo4j Username", metavar=""),
    passwd: str = typer.Option("password", "--pass", help="Neo4j Password", metavar=""),
    server: str = typer.Option(
        "127.0.0.1", "--server", help="Neo4j Server", metavar=""
    ),
    port: int = typer.Option(7474, "--port", help="Neo4j port", metavar=""),
):
    print(get_available_models())
