# -*- coding: latin-1 -*-

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from shiv.bootstrap import Environment
from shiv.builder import create_archive
from shiv.cli import __version__ as VERSION

PYZ_NAME = "ssbackend.pyz"


def build():
    try:
        os.mkdir("app")
        shutil.copytree("backend", "app/backend")
    except:
        shutil.rmtree("app")
        shutil.copytree("backend", "app/backend")

    shutil.copy("app.py", "app/main.py")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", ".", "-t", "app"],
        stdout=sys.stdout,
        stderr=subprocess.STDOUT,
    )

    [shutil.rmtree(p) for p in Path("app").glob("**/__pycache__")]
    [shutil.rmtree(p) for p in Path("app").glob("**/*.dist-info")]

    env = Environment(
        built_at=datetime.utcfromtimestamp(int(time.time())).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        entry_point="main:main",
        script=None,
        compile_pyc=False,
        extend_pythonpath=False,
        shiv_version=VERSION,
    )
    create_archive(
        [Path("app").absolute()],
        Path(PYZ_NAME),
        "/usr/bin/python3 -IS",
        "_bootstrap:bootstrap",
        env,
        True,
    )


if __name__ == "__main__":
    try:
        build()
    except:
        pass
    finally:
        pass
        # shutil.rmtree("app")
