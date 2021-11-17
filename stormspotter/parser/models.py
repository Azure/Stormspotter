from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, ClassVar

from pydantic import BaseModel


class RelationLabels(Enum):
    def _generate_next_value_(name, start, count, last_values):
        """Sets value of auto() to name of property"""
        return name

    ATTACHED = auto()
    AUTHENTICATES = auto()
    CONNECTEDTO = auto()
    EXPOSES = auto()
    HASACCESSPOLICIES = auto()
    HASMEMBER = auto()
    HASRBAC = auto()
    HASROLE = auto()
    MANAGES = auto()
    OWNER = auto()
    REPRESENTEDBY = auto()
    TRUSTS = auto()


class Node(BaseModel):
    """Base model for all nodes"""

    @property
    def _labels(self) -> Tuple[str, List[str]]:
        """Get the Neo4j labels for subclassed models"""

        label = self.__qualname__.split(".")[-1]
        if label == "Node":
            return None
        elif label in ["AADObject", "ARMResource"]:
            return (label.upper(), [])
        else:
            return (label.upper(), [type(self).mro()[1].__name__.upper()])

    class Config:
        extra = "ignore"
        underscore_attrs_are_private = True

        @classmethod
        def alias_generator(cls, value: str) -> str:
            """Converts source fields to fields for Neo4j"""
            return "".join(word.lower() for word in value.split("_"))


class Relationship(BaseModel):
    """Relationship model"""

    source: str
    source_label: str
    target: str
    target_label: str
    relation: RelationLabels
    properties: Optional[Dict[str, Any]]


class AADObject(Node):
    """Base Neo4JModel for AAD objects"""

    object_id: str
    displayname: str


class ARMResource(Node):
    """Base Neo4JModel for ARM resources"""

    # Set this to lowercase value of ARM type for dynamic object creation
    # i.e., microsoft.keyvault/vaults
    __arm_type__: ClassVar[str] = None

    id: str
    display_name: Optional[str]


class AADApplication(AADObject):
    application_id: str
    appownertenant_id: str
    enabled: bool
    homepage: Optional[str]
    _owners: List[str]


class AADServicePrincipal(AADObject):
    applicationid: str
    appownertenantid: str
    enabled: bool
    homepage: Optional[str]
    certcredcount: int
    passcredcount: int
    _owners: List[str]


class AADGroup(AADObject):
    onpremisessecurityidentifier: Optional[str] = ...
    securityenabled: bool
    _owners: List[str]
    _members: List[str]


class AADRole(AADObject):
    description: str
    deleteddatetime: Optional[str] = ...
    roletemplateid: str


class AADUser(AADObject):
    onpremisessecurityidentifier: Optional[str] = ...
    accountenabled: bool
    userprincipalname: str
    immutableid: str
    refreshtokensvalidfromdatetime: str


class Subscription(ARMResource):
    __arm_type__ = "subscription"

    tenant_id: str
    subscription_id: str
    state: str
    managed_by_tenants: Optional[List[str]] = ...
    tags: Optional[Dict[str, Any]] = ...


class Tenant(ARMResource):
    __arm_type__ = "tenant"

    tenant_id: str
    tenant_category: str
    country: str
    country_code: str
    domains: List[str]
    default_domain: str
    tenant_type: str
    tenant_branding_logo_url: str


def get_available_models() -> Dict[str, Node]:
    """Returns models available for Neo4j ingestion"""

    # AAD models need to use qualname or else you get ModelMetaclass back.
    aad_models = {c.__qualname__.split(".")[-1]: c for c in AADObject.__subclasses__()}
    arm_models = {c.__arm_type__: c for c in ARMResource.__subclasses__()}
    return aad_models | arm_models
