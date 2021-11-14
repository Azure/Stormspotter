from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Union

from azure.identity import AzureCliCredential, ClientSecretCredential
from msrestazure.azure_cloud import Cloud

from .enums import EnumMode


@dataclass
class CollectorContext:
    cred: Union[AzureCliCredential, ClientSecretCredential]
    cloud: Cloud
    mode: EnumMode
    backfill: bool
    include_subs: List[str]
    exclude_subs: List[str]
    output_dir: Path = Path(f"results_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
