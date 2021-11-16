from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Counter, List, Union
from uuid import UUID

from azure.identity import AzureCliCredential, ClientSecretCredential
from msrestazure.azure_cloud import Cloud

from .enums import EnumMode


@dataclass
class CollectorContext:
    """Dataclass for context during collection"""

    cred: Union[AzureCliCredential, ClientSecretCredential]
    cloud: Cloud
    mode: EnumMode
    backfill: bool
    include_subs: List[str]
    exclude_subs: List[str]
    tenant_id: Union[str, UUID] = "beta"
    output_dir: Path = Path(f"results_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    _aad_results: Counter = field(default_factory=Counter)
    _arm_results: Counter = field(default_factory=Counter)
