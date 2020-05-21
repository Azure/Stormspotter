# -*- coding: latin-1 -*-

import time
import shutil
import os
import sys
import pip
import distutils.sysconfig
from pathlib import Path
from datetime import datetime
from distutils.ccompiler import new_compiler
from shiv.builder import create_archive
from shiv.bootstrap import Environment
from shiv.cli import __version__ as VERSION

def build():
    try:
        os.mkdir("app")
        shutil.copytree("../stormspotter/collector", "app/stormspotter/collector")
    except:
        shutil.rmtree("app")
        shutil.copytree("../stormspotter", "app/stormspotter")

    shutil.copy("../stormspotter.py", "app/main.py")
    pip.main(["install", "-r", "requirements-collector.txt", "-t", "app"])

    [shutil.rmtree(p) for p in Path("app").glob("**/__pycache__")]
    [shutil.rmtree(p) for p in Path("app").glob("**/*.dist-info")]

    for pem in Path("../stormspotter/collector/certs").glob("*.pem"):
        with open(pem, 'rb') as infile:
            customca = infile.read()
        with open("app/certifi/cacert.pem", 'ab') as outfile:
            outfile.write(customca)
    
    env = Environment(
            built_at=datetime.utcfromtimestamp(int(time.time())).strftime("%Y-%m-%d %H:%M:%S"),
            entry_point="main:main",
            script=None,
            compile_pyc=False,
            extend_pythonpath=False,
            shiv_version=VERSION,
        )
    create_archive([Path("app").absolute()], Path("collector.pyz").expanduser(), "/usr/bin/env python3", "_bootstrap:bootstrap", env, True)

def compile():
    src = Path("stub.c")
    cc = new_compiler()
    exe = src.stem
    cc.add_include_dir(distutils.sysconfig.get_python_inc())
    cc.add_library_dir(os.path.join(sys.base_exec_prefix, 'libs'))
    # First the CLI executable
    objs = cc.compile([str(src)])
    cc.link_executable(objs, exe)
    os.remove("stub.obj")

def finalize():
    with open("collector.pyz", "rb") as pyz:
        with open("stub.exe", "rb") as stub:
            with open("collector.exe", "wb") as final:
                final.write(stub.read())
                final.write(pyz.read())
    
    shutil.rmtree("app")
    os.remove("stub.exe")
    
if __name__ == "__main__":
    build()
    compile()
    finalize()