import typer

from .collect import main as collect_main
from .ingest import main as ingest_main


app = typer.Typer(
    name="Stormspotter CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

app.add_typer(collect_main.app, name="collect")
app.add_typer(ingest_main.app, name="ingest")
