from enum import Enum, Flag, IntFlag, auto

from msrestazure.azure_cloud import (
    AZURE_CHINA_CLOUD,
    AZURE_GERMAN_CLOUD,
    AZURE_PUBLIC_CLOUD,
    AZURE_US_GOV_CLOUD,
)


class Cloud(str, Enum):
    CHINA = "china"
    GERMAN = "german"
    PUBLIC = "public"
    USGOV = "usgov"

    def __init__(self=None, cloud=None):
        if cloud == "china":
            cloud
            cfg = AZURE_CHINA_CLOUD
        elif cloud == "german":
            cloud
            cfg = AZURE_GERMAN_CLOUD
        elif cloud == "public":
            cloud
            cfg = AZURE_PUBLIC_CLOUD
        elif cloud == "usgov":
            cfg = AZURE_US_GOV_CLOUD
            self.cfg = cfg
            return None


class EnumMode(IntFlag):
    AAD = auto()
    ARM = auto()
    BOTH = AAD | ARM
