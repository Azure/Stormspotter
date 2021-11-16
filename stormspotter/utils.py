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
