import setuptools
import shutil
from pathlib import Path
from pkg_resources import resource_filename

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stormspotter", # Replace with your own username
    version="1.0.0a",
    author="Azure Red Team",
    description="Azure Red Team tool for graphing Azure and Azure Active Directory objects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Azure/Stormspotter",
    packages=["stormspotter"],
    install_requires = [
        "azure-cli-core==2.5.1",
        "azure-mgmt-authorization==0.60.0",
        "azure-mgmt-core==1.0.0",
        "azure-mgmt-resource==9.0.0",
        "dash==1.12.0",
        "dash-bootstrap-components==0.9.2",
        "dash-cytoscape==0.1.1",
        "dash-daq==0.5.0",
        "neo4j==1.7.6",
        "pkginfo==1.5.0.1",
        "shiv==0.1.2",
        "watchdog==0.10.2"
    ],
    py_modules=["Stormdash", "Stormspotter"],
    include_package_data=True,
    entry_points={
          'console_scripts': [
              'stormspotter = Stormspotter:main',
              'stormdash = Stormdash:main'
          ]
      },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
        "Framework :: Dash",
        "License :: OSI Approved :: MIT License"
    ],
    python_requires='>=3.8',
)

Path("~/.stormspotter/input").expanduser().mkdir(parents=True, exist_ok=True)
Path("~/.stormspotter/processed").expanduser().mkdir(parents=True, exist_ok=True)

try:
    shutil.copy(resource_filename(__name__, "stormspotter/cloud.cfg"),
                Path("~/.stormspotter/cloud.cfg").expanduser())
except FileNotFoundError:
    shutil.copy(resource_filename(__name__, "cloud.cfg"),
                Path("~/.stormspotter/cloud.cfg").expanduser())