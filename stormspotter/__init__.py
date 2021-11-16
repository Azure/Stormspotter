import logging
import sys

from rich import pretty, traceback
from rich.logging import RichHandler

from .utils import proactor_win32_patch

if sys.platform == "nix":
    import uvloop

    uvloop.install()
elif sys.platform == "win32":
    sys.unraisablehook = proactor_win32_patch

traceback.install()
pretty.install()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
