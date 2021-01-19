# -*- coding: latin-1 -*-

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

# import distutils.sysconfig
from pathlib import Path

from shiv.bootstrap import Environment

# from distutils.ccompiler import new_compiler
from shiv.builder import create_archive
from shiv.cli import __version__ as VERSION

PYZ_NAME = "sscollector.pyz"


def build():
    try:
        os.mkdir("app")
        shutil.copytree("stormcollector", "app/stormcollector")
    except:
        shutil.rmtree("app")
        shutil.copytree("stormcollector", "app/stormcollector")

    shutil.copy("sscollector.py", "app/main.py")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", ".", "-t", "app"],
        stdout=sys.stdout,
        stderr=subprocess.STDOUT,
    )

    [shutil.rmtree(p) for p in Path("app").glob("**/__pycache__")]
    [shutil.rmtree(p) for p in Path("app").glob("**/*.dist-info")]

    for pem in Path("certs").glob("*.pem"):
        with open(pem, "rb") as infile:
            customca = infile.read()
        with open("app/certifi/cacert.pem", "ab") as outfile:
            outfile.write(customca)

    env = Environment(
        built_at=datetime.utcfromtimestamp(int(time.time())).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        entry_point="main:main",
        script=None,
        compile_pyc=False,
        extend_pythonpath=True,
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


# def compile():
#     src = Path("stub.c")
#     cc = new_compiler()
#     exe = src.stem
#     cc.add_include_dir(distutils.sysconfig.get_python_inc())
#     cc.add_library_dir(os.path.join(sys.base_exec_prefix, 'libs'))
#     # First the CLI executable
#     objs = cc.compile([str(src)])
#     cc.link_executable(objs, exe)
#     os.remove("stub.obj")

# def finalize():
#     with open("collector.pyz", "rb") as pyz:
#         with open("stub.exe", "rb") as stub:
#             with open("collector.exe", "wb") as final:
#                 final.write(stub.read())
#                 final.write(pyz.read())

# shutil.rmtree("app")
# os.remove("stub.exe")

if __name__ == "__main__":
    try:
        build()
    except:
        pass
    finally:
        shutil.rmtree("app")
    # compile()
    # finalize()
