from dataclasses import dataclass, field
from typing import List
from msrestazure.azure_cloud import AZURE_PUBLIC_CLOUD
from stormspotter.collector.utils.resources import *

@dataclass
class AADObject():
    resource = str
    node_label: str = AADOBJECT_NODE_LABEL
    query_parameters: List = field(default_factory= lambda: [])
    api_version: str = "1.6-internal"

    def parse(self, tenant_id, value, context):
        return value
    
    def expand(self, tenant_id, resource_id, prop, context):
        session = context.auth.aad_cred.signed_session()
        user_url = "{}{}/{}/{}/{}?{}".format(
            AZURE_PUBLIC_CLOUD.endpoints.active_directory_graph_resource_id, tenant_id,
            self.resource, resource_id, prop, f"api-version={self.api_version}")
        return session.get(user_url).json() 
        
    def generate_query_params(self, parameters, api_version):
        parameters.append(f"api-version={self.api_version}")
        return "&".join(parameters)

    def query_resources(self, context):
        resources = [self.node_label]
        print(f"Starting query for {self.node_label}")
        cred = context.auth.aad_cred
        tenant_id = context.auth.tenant_id

        session = cred.signed_session()
        query_params = self.generate_query_params(
            self.query_parameters, self.api_version)
        user_url = "{}{}/{}?{}".format(
            AZURE_PUBLIC_CLOUD.endpoints.active_directory_graph_resource_id,
            tenant_id, self.resource, query_params)
        next_link = True
        while next_link:
            response = session.get(user_url).json()
            for val in response["value"]:
                parsedVal = self.parse(tenant_id, val, context)
                resources.append(parsedVal)
            if "odata.nextLink" in response:
                user_url = "{}{}/{}&api-version={}".format(
                    AZURE_PUBLIC_CLOUD.endpoints.
                    active_directory_graph_resource_id, tenant_id,
                    response["odata.nextLink"], self.api_version)
            else:
                next_link = False
        print (f"Finished query for {self.node_label}")
        return resources

    def parse_dict(self, dict_obj, prop, lower=True):
        if not prop in dict_obj:
            return None
        obj = dict_obj[prop]
        if obj and type(obj) == str:
            obj = obj.replace("'", "\\'")
            if lower:
                obj = obj.lower()
        return obj
