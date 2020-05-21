"""import various contexts"""
from .cloud import CloudContext
from .context import context
from .authentication import Authentication

from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
from datetime import datetime

SSC = context()
Recorder = ZipFile(f"results.zip", "w", compression=ZIP_DEFLATED)
