import logging
import sys

from rich import pretty, traceback

from .utils import proactor_win32_patch

if sys.platform == "nix":
    import uvloop

    uvloop.install()
elif sys.platform == "win32":
    sys.unraisablehook = proactor_win32_patch

traceback.install()
pretty.install()

# Reduce some logging
# Reduce Azure HTTP logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
