import configparser
from argparse import Namespace
from typing import IO, Any, Tuple

import azure.identity as identity
import azure.identity.aio as identity_aio
from loguru import logger

from .adapter import AzureIdentityCredentialAdapter

CLOUD_MAP = {
    "PUBLIC": {
        "AD": identity.KnownAuthorities.AZURE_PUBLIC_CLOUD,
        "AAD": "https://graph.windows.net",
        "ARM": "https://management.azure.com",
        "GRAPH": "https://graph.microsoft.com",
        "MGMT": "https://management.core.windows.net",
    },
    "GERMAN": {
        "AD": identity.KnownAuthorities.AZURE_GERMANY,
        "AAD": "https://graph.cloudapi.de",
        "ARM": "https://management.microsoftazure.de",
        "GRAPH": "https://graph.microsoft.de",
        "MGMT": "https://management.core.cloudapi.de",
    },
    "CHINA": {
        "AD": identity.KnownAuthorities.AZURE_CHINA,
        "AAD": "https://graph.chinacloudapi.cn",
        "ARM": "https://management.chinacloudapi.cn",
        "GRAPH": "https://microsoftgraph.chinacloudapi.cn",
        "MGMT": "https://management.core.chinacloudapi.cn",
    },
    "USGOV": {
        "AD": identity.KnownAuthorities.AZURE_GOVERNMENT,
        "AAD": "https://graph.windows.net",
        "ARM": "https://management.usgovcloudapi.net",
        "GRAPH": "https://graph.microsoft.us/",
        "MGMT": "https://management.core.usgovcloudapi.net",
    },
}


class Context:
    def __init__(
        self,
        args: Namespace,
        cloud: dict,
        authenticatedCreds: Tuple[Any],
    ):
        self.args = args
        self.cloud = cloud
        self.cred_sync, self.cred_async, self.cred_msrest = authenticatedCreds

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
            custom["GRAPH"] = cfg["ENDPOINTS"]["MS_Graph"]
            custom["MGMT"] = cfg["ENDPOINTS"]["Management"]
            return custom
        return CLOUD_MAP[cloud]

    @staticmethod
    def _get_resource_creds_from_cli(
        cloud: dict, args: Namespace
    ) -> Tuple[identity.AzureCliCredential, identity_aio.AzureCliCredential]:
        """Get credentials using CLI Credentials"""
        try:
            logger.info(f"Authenticating to {cloud['AD']} with CLI credentials.")
            return [
                identity.AzureCliCredential(),
                identity_aio.AzureCliCredential(),
            ]

        except Exception as e:
            logger.warning(e)
            exit()

    @staticmethod
    def _get_resource_creds_from_spn(
        cloud: dict, args: Namespace
    ) -> Tuple[identity.ClientSecretCredential, identity_aio.ClientSecretCredential]:
        """Get credentials using Service Principal Credentials"""
        try:
            logger.info(
                f"Authenticating to {cloud['AD']} with Service Principal credentials."
            )
            return [
                identity.ClientSecretCredential(
                    args.tenantid, args.clientid, args.secret, authority=cloud["AD"]
                ),
                identity_aio.ClientSecretCredential(
                    args.tenantid, args.clientid, args.secret, authority=cloud["AD"]
                ),
            ]
        except Exception as e:
            logger.warning(e)
            exit()

    @staticmethod
    async def auth(args: Namespace, currentCtx=None):
        """Authenticate to AAD and/or ARM endpoints}"""

        # Minimize repeated code by calling functions dynamically
        auth_func = {
            "cli": Context._get_resource_creds_from_cli,
            "spn": Context._get_resource_creds_from_spn,
        }

        cloud = Context._get_auth_cloud(args.cloud, args.config)
        authenticatedCreds = auth_func[args.auth](cloud, args)
        adaptedCred = AzureIdentityCredentialAdapter(
            authenticatedCreds[0], cloud["ARM"] + "/.default"
        )

        authenticatedCreds.append(adaptedCred)
        if currentCtx:
            return authenticatedCreds

        return Context(args, cloud, authenticatedCreds)
