import sys


def proactor_win32_patch(event):
    """Ignores Proactor loop errors on Windows"""
    if (
        event.exc_type == RuntimeError
        and str(event.exc_value) == "Event loop is closed"
    ):
        pass
    else:
        sys.__unraisablehook__(event)


def qualname_base(some_instance) -> str:
    return some_instance.__qualname__.split(".")[-1]
