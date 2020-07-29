import configparser
from loguru import logger
from argparse import Namespace
from typing import IO, Any, Union

from azure.identity import KnownAuthorities
from azure.identity.aio import AzureCliCredential, ClientSecretCredential

CLOUD_MAP = {
    "PUBLIC": {
        "AD": KnownAuthorities.AZURE_PUBLIC_CLOUD,
        "AAD": "https://graph.windows.net",
        "ARM": "https://management.azure.com",
    },
    "GERMAN": {
        "AD": KnownAuthorities.AZURE_GERMANY,
        "AAD": "https://graph.cloudapi.de",
        "ARM": "https://management.microsoftazure.de",
    },
    "CHINA": {
        "AD": KnownAuthorities.AZURE_PUBLIC_CLOUD,
        "AAD": "https://graph.chinacloudapi.cn",
        "ARM": "https://management.chinacloudapi.cn",
    },
    "USGOV": {
        "AD": KnownAuthorities.AZURE_PUBLIC_CLOUD,
        "AAD": "https://graph.windows.net",
        "ARM": "https://management.usgovcloudapi.net",
    },
}


class Context:
    def __init__(
        self,
        cloud: dict,
        authenticatedCred: Union[AzureCliCredential, ClientSecretCredential],
    ):
        self.cloud = cloud
        self.cred = authenticatedCred

    @staticmethod
    def _get_auth_cloud(cloud: str, config: IO[Any] = None) -> str:
        """Return the cloud environment used for authentication"""
        if config:
            cfg = configparser.ConfigParser()
            cfg.read_file(config)

            custom = {}
            custom["ARM"] = cfg["ENDPOINTS"]["Resource_Manager"]
            custom["AD"] = cfg["ENDPOINTS"]["AD"]
            custom["AAD"] = cfg["ENDPOINTS"]["AD_Graph_ResourceId"]
            return custom
        return CLOUD_MAP[cloud]

    @staticmethod
    def _get_resource_creds_from_cli(
        cloud: dict, args: Namespace
    ) -> AzureCliCredential:
        """Get credentials using CLI Credentials"""
        try:
            logger.info(f"Authenticating to {cloud['AD']} ")
            return AzureCliCredential()

        except Exception as e:
            logger.warning(e)
            return None

    @staticmethod
    def _get_resource_creds_from_spn(
        resource: dict, args: Namespace
    ) -> ClientSecretCredential:
        """Get credentials using Service Principal Credentials"""
        try:
            return ServicePrincipalCredentials(
                client_id=args.clientid,
                secret=args.secret,
                resource=resource,
                tenant=args.tenantid,
            )
        except Exception as e:
            logger.warning(e)
            return None

    @staticmethod
    async def auth(args: Namespace):
        """Authenticate to AAD and/or ARM endpoints}"""

        # Minimize repeated code by calling functions dynamically
        auth_func = {
            "cli": Context._get_resource_creds_from_cli,
            "spn": Context._get_resource_creds_from_spn,
        }

        cloud = Context._get_auth_cloud(args.cloud, args.config)
        authenticatedCred = auth_func[args.auth](cloud, args)
        return Context(cloud, authenticatedCred)
