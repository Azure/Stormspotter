from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel
from rich import print


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

    @classmethod
    def _labels(cls) -> Tuple[str, List[str]]:
        """Get the Neo4j labels for subclassed models"""

        label = cls.__qualname__.split(".")[-1]
        if label == "Node":
            return None
        elif label in ["AADObject", "ARMResource"]:
            return (label.upper(), [])
        else:
            return (label.upper(), [cls.__mro__[1].__name__.upper()])

    class Config:
        extra = "ignore"


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

    id: str
    displayName: str


class ARMResource(Node):
    """Base Neo4JModel for ARM resources"""

    # Set this to lowercase value of ARM type for dynamic object creation
    # i.e., microsoft.keyvault/vaults
    __arm_type__: ClassVar[str] = None

    id: str
    display_name: Optional[str]

    # class Config:
    #     @classmethod
    #     def alias_generator(cls, value: str) -> str:
    #         """Converts source fields to fields for Neo4j"""
    #         return "".join(word.lower() for word in value.split("_"))


####--- AAD RELATED MODELS ---###
class AADApplication(AADObject):
    appId: str
    appOwnerOrganizationId: Optional[str]
    owners: List[str]
    publisherName: Optional[str]


class AADServicePrincipal(AADObject):
    accountEnabled: bool
    appDisplayName: Optional[str] = ...
    appId: str
    appOwnerOrganizationId: Optional[str] = ...
    owners: List[str]
    publisherName: Optional[str] = ...
    servicePrincipalType: str


class AADGroup(AADObject):
    members: List[str]
    onPremisesSecurityIdentifier: Optional[str] = ...
    owners: List[str]
    securityEnabled: bool


class AADRole(AADObject):
    description: str
    deletedDateTime: Optional[str] = ...
    roleTemplateId: str
    members: List[str]


class AADUser(AADObject):
    accountEnabled: bool
    mail: Optional[str] = ...
    onPremisesDistinguishedName: Optional[str] = ...
    onPremisesDomainName: Optional[str] = ...
    onPremisesSamAccountName: Optional[str] = ...
    onPremisesSecurityIdentifier: Optional[str] = ...
    onPremisesUserPrincipalName: Optional[str] = ...
    refreshTokensValidFromDateTime: str
    userPrincipalName: str
    userType: str


####--- ARM RELATED MODELS ---###
class Tenant(ARMResource):
    __arm_type__ = "tenant"

    tenant_id: str
    tenant_category: str
    country_code: str
    domains: List[str]
    default_domain: str
    tenant_type: str


class Subscription(ARMResource):
    __arm_type__ = "subscription"

    tenant_id: str
    subscription_id: str
    state: str
    managed_by_tenants: Optional[List[str]] = ...


def get_available_models() -> Dict[str, Node]:
    """Returns models available for Neo4j ingestion"""

    # AAD models need to use qualname or else you get ModelMetaclass back.
    aad_models = {c.__qualname__.split(".")[-1]: c for c in AADObject.__subclasses__()}
    arm_models = {c.__arm_type__: c for c in ARMResource.__subclasses__()}
    return aad_models | arm_models


def get_all_labels() -> List[str]:
    """Returns a list of all labels from all available models"""
    models = get_available_models()
    return list(set([model._labels()[0] for model in models.values()]))
