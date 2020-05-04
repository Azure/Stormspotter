from dataclasses import dataclass, field
from typing import List
from .aadobject import AADObject
from stormspotter.ingestor.utils.resources import *

@dataclass
class AADGroup(AADObject):
    resource: str = "groups"
    node_label: str = AADGROUP_NODE_LABEL
    query_parameters: List = field(default_factory= lambda: [])
    api_version: str = "1.6-internal"

    def parse(self, tenant_id, value, context):
        members = self.expand(tenant_id, value["objectId"], "members", context)
        member_ids = [member['objectId'] for member in members["value"]]

        owners = self.expand(tenant_id, value["objectId"], "owners", context)
        owner_ids = [owner['objectId'] for owner in owners["value"]]

        
        value["members"] = member_ids
        value["owners"] = owner_ids
        return value
        #context.neo4j.insert_asset(obj, AADOBJECT_NODE_LABEL, obj["objectid"], [AADGROUP_NODE_LABEL])
        #if "members" in value:
        #    for member in value["members"]:
        #        context.neo4j.create_relationship(member["objectId"],
        #                                          AADOBJECT_NODE_LABEL, obj["objectid"],
        #                                          AADGROUP_NODE_LABEL, USER_TO_GROUP)
