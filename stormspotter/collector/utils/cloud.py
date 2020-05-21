""" Handes the cloud context part of the stormspotter context"""
import configparser
from msrestazure.azure_cloud import Cloud, CloudEndpoints, CloudSuffixes, AZURE_PUBLIC_CLOUD, AZURE_GERMAN_CLOUD, AZURE_CHINA_CLOUD, AZURE_US_GOV_CLOUD

class CloudContext:
    """
    Specifies which endpoints based on cloud instance for authentication purposes
    """
    def __init__(self, cloud, config=None):
        configuration = configparser.ConfigParser()
        if config:
            # read config file and make Cloud object
            configuration.read(config)
            name = configuration['NAME']['Cloud']
            self.cloud = Cloud(
                name,
                endpoints=CloudEndpoints(
                    management=configuration['ENDPOINTS']['Management'],
                    resource_manager=configuration['ENDPOINTS']['Resource_Manager'],
                    sql_management=configuration['ENDPOINTS']['SQL_Management'],
                    batch_resource_id=configuration['ENDPOINTS']['Batch_ResourceId'],
                    gallery=configuration['ENDPOINTS']['Gallery'],
                    active_directory=configuration['ENDPOINTS']['AD'],
                    active_directory_resource_id=configuration['ENDPOINTS']['AD_ResourceId'],
                    active_directory_graph_resource_id=configuration['ENDPOINTS']['AD_Graph_ResourceId']
                ),
                suffixes=CloudSuffixes(
                    storage_endpoint=configuration['SUFFIXES']['Storage_Endpoint'],
                    keyvault_dns=configuration['SUFFIXES']['Keyvault_DNS'],
                    sql_server_hostname=configuration['SUFFIXES']['SQLServer_Hostname'],

                )
            )
        else:
            if cloud == 'GERMANY':
                self.cloud = AZURE_GERMAN_CLOUD
            elif cloud == 'CHINA':
                self.cloud = AZURE_CHINA_CLOUD
            elif cloud == 'USGOV':
                self.cloud = AZURE_US_GOV_CLOUD
            elif cloud == 'PUBLIC':
                self.cloud = AZURE_PUBLIC_CLOUD
            