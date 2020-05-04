from dataclasses import dataclass, field
from typing import List
from .aadobject import AADObject
from stormspotter.ingestor.utils.resources import *

@dataclass
class AADApplication(AADObject):
    resource = "applications"
    node_label: str = AADAPP_NODE_LABEL
    query_parameters: List = field(default_factory= lambda: ["$expand=owners"])
    api_version: str = "1.6-internal"
    
    def parse(self, tenant_id, value, context):
        owners = self.expand(tenant_id, value["objectId"], "owners", context)
        owner_ids = [owner['objectId'] for owner in owners["value"]]

        value["owners"] = owner_ids
        return value
        #context.neo4j.insert_asset(obj, AADOBJECT_NODE_LABEL, obj["objectid"], [AADAPP_NODE_LABEL])
        #if "owners" in value:
        #    for owner in value["owners"]:
        #        context.neo4j.create_relationship(owner["objectId"],
        #                                          AADOBJECT_NODE_LABEL, obj["objectid"],
        #                                          AADAPP_NODE_LABEL, AAD_TO_ASSET)
        