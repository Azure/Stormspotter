from dataclasses import dataclass, field
from typing import List
from .aadobject import AADObject
from stormspotter.collector.utils.resources import *

@dataclass
class AADUser(AADObject):
    resource: str = "users"
    node_label: str = AADUSER_NODE_LABEL
    query_parameters: List = field(default_factory= lambda: [])
    api_version: str = "1.6-internal"

    def parse(self, tenant_id, value, context):
        return value
        #context.neo4j.insert_asset(obj, AADOBJECT_NODE_LABEL, obj["objectid"], [AADUSER_NODE_LABEL])
