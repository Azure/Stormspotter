"""Handles authentication to Graph and Azure resources"""
from azure.common.credentials import ServicePrincipalCredentials

class Authentication():
    """
    Allows user to authenticate using a service prinicpal or their identity
    using the azure cli
    """
    resource_cred = None
    aad_cred = None
    tenant_id = None
    subscriptions = []

    def __init__(self, cli, serviceprincipal, appid=None, password=None, tenant=None):
        from stormspotter.collector.utils import SSC as context

        GRAPH_RESOURCE = context.cloudContext.cloud.endpoints.active_directory_graph_resource_id
        ARM_RESOURCE = context.cloudContext.cloud.endpoints.active_directory_resource_id

        if cli:
            self.resource_cred = self.authenticate_from_cli(ARM_RESOURCE)
            self.aad_cred = self.authenticate_from_cli(GRAPH_RESOURCE)
        elif serviceprincipal and appid and password and tenant:
            self.tenant_id = tenant
            self.resource_cred = self.get_spn_credentials(
                appid, password, tenant, ARM_RESOURCE)
            self.aad_cred = self.get_spn_credentials(
                appid, password, tenant, GRAPH_RESOURCE)

    def authenticate_from_cli(self, resource):
        """
        Create the azure resource manager client from the user logged into azure cli
        If a user is not logged in the run the az login command so they can authenticate
        """
        print(f"Attempting to get cli credentials for resource {resource}")
        from azure.common.credentials import get_azure_cli_credentials

        try:
            credential, subscription_id, self.tenant_id = get_azure_cli_credentials(
                resource=resource, with_tenant=True)
        except:
            print("We were not able to find a cli profile attempting to login")
            from subprocess import run
            import platform

            shell = platform.system() == "Windows"
            run(["az", "login", "--use-device-code"], shell=shell)
            return self.authenticate_from_cli(resource)
        return credential

    def get_spn_credentials(self, appid, password, tenantid, resource_uri):
        """
        Return the ServicePrincipalCredentials
        """
        print("Attemprint to get CLI Credentials from a Service Principal")
        return ServicePrincipalCredentials(
            client_id=appid,
            secret=password,
            tenant=tenantid,
            resource=resource_uri)
