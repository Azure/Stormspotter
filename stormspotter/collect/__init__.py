import logging
import sys

from rich import pretty, traceback
from rich.logging import RichHandler

if sys.platform == "nix":
    import uvloop

    uvloop.install()

traceback.install()
pretty.install()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
