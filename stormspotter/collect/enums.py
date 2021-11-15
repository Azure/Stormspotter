from enum import Enum, IntFlag, auto

from msrestazure.azure_cloud import (AZURE_CHINA_CLOUD, AZURE_GERMAN_CLOUD,
                                     AZURE_PUBLIC_CLOUD, AZURE_US_GOV_CLOUD)


class Cloud(str, Enum):
    CHINA = "china"
    GERMAN = "german"
    PUBLIC = "public"
    USGOV = "usgov"

    def __init__(self=None, cloud=None):
        if cloud == "china":
            cloud
            _cloud = AZURE_CHINA_CLOUD
        elif cloud == "german":
            cloud
            _cloud = AZURE_GERMAN_CLOUD
        elif cloud == "public":
            cloud
            _cloud = AZURE_PUBLIC_CLOUD
        elif cloud == "usgov":
            _cloud = AZURE_US_GOV_CLOUD

        self._cloud = _cloud


class EnumMode(IntFlag):
    AAD = auto()
    ARM = auto()
    BOTH = AAD | ARM
