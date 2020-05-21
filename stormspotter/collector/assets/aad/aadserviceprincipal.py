from dataclasses import dataclass, field
from typing import List
from .aadobject import AADObject
from stormspotter.collector.utils.resources import *

@dataclass
class AADServicePrincipal(AADObject):
    resource = "servicePrincipals"
    node_label: str = AADSPN_NODE_LABEL
    query_parameters: List = field(default_factory= lambda: [])
    api_version: str = "1.6-internal"

    def parse(self, tenant_id, value, context):
        if not value["microsoftFirstParty"]:
            owners = self.expand(tenant_id, value["objectId"], "owners", context)
            owner_ids = [owner['objectId'] for owner in owners["value"]]

            value["owners"] = owner_ids
        else:
            value["owners"] = []
        return value
        #context.neo4j.insert_asset(obj, AADOBJECT_NODE_LABEL, obj["objectid"], [AADSPN_NODE_LABEL])
        #if obj["owners"]:
        #    for owner in value["owners"]:
        #        context.neo4j.create_relationship(owner["objectId"],
         #                                         AADOBJECT_NODE_LABEL, obj["objectid"],
         #                                         AADSPN_NODE_LABEL, AAD_TO_ASSET)
                                                  