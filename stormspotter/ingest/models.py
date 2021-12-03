import json
import logging
from enum import Enum, auto
from operator import attrgetter
from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator
from pydantic.fields import PrivateAttr
from rich import inspect, print

from ..utils import qualname_base

log = logging.getLogger("rich")


class DynamicObject:
    def __init__(self, d: dict) -> None:
        self.__dict__.update(d)

    def __getattr__(self, item: str):
        return self.__dict__[item]

    def __dir__(self):
        return [self.__dict__.keys()]

    def __repr__(self) -> str:
        return str(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "DynamicObject":
        return json.loads(json.dumps(d, default={}), object_hook=DynamicObject)


class RelationLabels(Enum):
    def _generate_next_value_(name, start, count, last_values):
        """Sets value of auto() to name of property"""
        return name

    AttachedTo = auto()
    Authenticates = auto()
    ConnectedTo = auto()
    Contains = auto()
    Exposes = auto()
    HasAccessPolicies = auto()
    HasRbac = auto()
    HasRole = auto()
    Manages = auto()
    MemberOf = auto()
    Owns = auto()
    RepresentedBy = auto()
    Trusts = auto()


class Relationship(BaseModel):
    """Relationship model"""

    source: str
    source_label: str
    target: str
    target_label: str
    relation: Union[RelationLabels, str]
    properties: Optional[Dict[str, Any]]

    @validator("properties", pre=True, always=True)
    def format_properties(cls, props: Any):
        """Convert DynamicObject to dict"""
        if isinstance(props, dict):
            return props
        elif isinstance(props, DynamicObject):
            return props.__dict__

    def to_neo(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"properties"})

    def getattr(self, attr: str) -> Any:
        """Returns an object attribute if exists"""
        try:
            return attrgetter(attr)(self)
        except:
            return None


class Rbac:
    pass


class Node(BaseModel):
    """Base model for all nodes"""

    _relationships: List[Relationship] = PrivateAttr(default_factory=list)

    # A. Ignore all extra fields
    # B. Encode DynamicObject by getting the __dict__
    class Config:
        extra = "ignore"
        json_encoders = {DynamicObject: lambda v: v.__dict__}

    def __relationships__(self) -> List[Relationship]:
        """Override this method to define relationships for resource object."""
        return

    @classmethod
    def _labels(cls) -> List[str]:
        """Get the Neo4j labels for subclassed models"""

        label = cls.__qualname__.split(".")[-1]
        if label == "Node":
            return None
        elif label in ["AADObject", "ARMResource"]:
            return [label.upper()]
        else:
            return [cls.__mro__[1].__name__.upper(), label.upper()]

    @property
    def label(self) -> str:
        return qualname_base(self).upper()

    def to_neo(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"properties"})

    def getattr(self, attr: str) -> Any:
        """Returns an object attribute if exists"""
        try:
            return attrgetter(attr)(self)
        except:
            return None


####--- AAD RELATED MODELS ---###
class AADObject(Node):
    """Base Neo4JModel for AAD objects"""

    id: str
    displayName: str

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # Process owner relations
        # Member is a UUID string that represents an AADObject
        for owner in getattr(self, "owners", []):
            self._relationships.append(
                Relationship(
                    source=owner,
                    source_label=self._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.Owns,
                )
            )
        # Process member relations
        # Member is a UUID string that represents an AADObject
        for member in getattr(self, "members", []):
            self._relationships.append(
                Relationship(
                    source=member,
                    source_label=AADObject._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.MemberOf,
                )
            )
        if additional_rels := self.__relationships__():
            self._relationships.extend(additional_rels)

    def to_neo(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"owners", "members"}) | {
            "_relationships": self._relationships
        }


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
    organizationId: str
    owners: List[str]
    securityEnabled: bool


class AADRole(AADObject):
    description: str
    deletedDateTime: Optional[str] = ...
    roleTemplateId: str
    members: List[str]


class AADUser(AADObject):
    accountEnabled: bool
    creationType: Optional[str] = ...
    mail: Optional[str] = ...
    mailNickname: Optional[str] = ...
    onPremisesDistinguishedName: Optional[str] = ...
    onPremisesDomainName: Optional[str] = ...
    onPremisesExtensionAttributes: Optional[List[str]] = Field(default_factory=list)
    onPremisesSamAccountName: Optional[str] = ...
    onPremisesSecurityIdentifier: Optional[str] = ...
    onPremisesUserPrincipalName: Optional[str] = ...
    refreshTokensValidFromDateTime: str
    userPrincipalName: str
    userType: str

    @validator("onPremisesExtensionAttributes", pre=True, always=True)
    def exattr_to_values_list(cls, dict_value: dict):
        """Convert extension attributes to list of their values"""
        return list(filter(None, dict_value.values()))


####--- ARM RELATED MODELS ---###
class ARMResource(Node):
    """Base Neo4JModel for ARM resources"""

    # Set this to lowercase value of ARM type for dynamic object creation
    # i.e., microsoft.keyvault/vaults
    __arm_type__: ClassVar[str] = ...
    __xfields__: ClassVar[List[str]] = PrivateAttr(default_factory=list)
    __map_to_resourcegroup__: ClassVar[bool] = True
    __xdict__: Dict[str, Any] = PrivateAttr(default_factory=dict)

    id: str
    location: Optional[str]
    name: Optional[str]
    properties: Optional[DynamicObject]
    tags: Optional[List[str]]

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # Grab the field from the properties and set it as it's own property
        if self.properties and self.__xfields__:
            for field in self.__xfields__:
                try:
                    value = attrgetter(field)(self.properties)
                except:
                    value = None

                field_name = field.split(".")[-1]
                self.__xdict__[field_name] = value

        # Add default resource group relationship
        if self.__map_to_resourcegroup__:
            self._relationships.append(
                Relationship(
                    source=self.resourcegroup,
                    source_label=ResourceGroup._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.Contains,
                )
            )

        if additional_rels := self.__relationships__():
            self._relationships.extend(additional_rels)

    @property
    def subscription(self) -> str:
        """Get the subscription from the id"""
        return self.id.split("/resourceGroups")[0]

    @property
    def resourcegroup(self) -> str:
        """Get the resource group from the id"""
        return self.id.split("/providers")[0]

    @validator("tags", pre=True, always=True)
    def convert_to_list(cls, dict_value: dict):
        """Convert tags dictionary to list for neo4j property"""
        if dict_value:
            as_list = []
            [as_list.extend([k, v]) for k, v in dict_value.items()]
            return as_list
        return None

    @validator("properties", pre=True, always=True)
    def props_to_obj(cls, dict_value: str):
        """Convert properties dictionary to dynamic object"""
        return DynamicObject.from_dict(dict_value)

    def node(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return (
            self.dict(exclude={"properties"})
            | self.__xdict__
            | {"_relationships": self._relationships}
        )


class Tenant(ARMResource):
    __arm_type__ = "tenant"
    __map_to_resourcegroup__ = False

    tenant_id: str
    tenant_category: str
    country_code: str
    domains: List[str]
    default_domain: str
    tenant_type: str


class Subscription(ARMResource):
    __arm_type__ = "subscription"
    __map_to_resourcegroup__: ClassVar[bool] = False

    tenant_id: str
    name: str = Field(alias="display_name")
    subscription_id: str
    state: str
    managed_by_tenants: Optional[List[str]] = Field(default_factory=list)

    def __relationships__(self) -> List[Relationship]:
        relations = []
        relations.append(
            Relationship(
                source="/tenants/" + self.tenant_id,
                source_label=Tenant._labels()[0],
                target=self.id,
                target_label=self._labels()[0],
                relation=RelationLabels.Contains,
            )
        )
        return relations


class ResourceGroup(ARMResource):
    __arm_type__ = "microsoft.resources/resourcegroups"
    __map_to_resourcegroup__: ClassVar[bool] = False

    def __relationships__(self) -> List[Relationship]:
        relations = []
        relations.append(
            Relationship(
                source=self.subscription,
                source_label=Subscription._labels()[0],
                target=self.id,
                target_label=self._labels()[0],
                relation=RelationLabels.Contains,
            )
        )
        return relations


class KeyVault(ARMResource):
    __arm_type__ = "microsoft.keyvault/vaults"
    __xfields__ = [
        "enableSoftDelete",
        "softDeleteRetentionInDays",
        "enableRbacAuthorization",
        "enablePurgeProtection",
        "vaultUri",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        for policy in self.properties.accessPolicies:
            relations.append(
                Relationship(
                    source=policy.objectId,
                    source_label=AADObject._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.HasAccessPolicies,
                    properties=policy.permissions,
                )
            )
        return relations


class StorageAccount(ARMResource):
    __arm_type__ = "microsoft.storage/storageaccounts"
    __xfields__ = ["accessTier", "creationTime", "supportsHttpsTrafficOnly"]


def get_available_models() -> Dict[str, Node]:
    """Returns models available for Neo4j ingestion"""

    # AAD models need to use qualname or else you get ModelMetaclass back.
    aad_models = {qualname_base(c): c for c in AADObject.__subclasses__()}
    arm_models = {c.__arm_type__: c for c in ARMResource.__subclasses__()}
    return aad_models | arm_models | {"rbac": Rbac}


def get_all_labels() -> List[str]:
    """Returns a list of all labels from all available models"""
    models = AVAILABLE_MODELS
    return list(
        set(
            [
                model._labels()[-1]
                for model in models.values()
                if hasattr(model, "_labels")
            ]
        )
    )


AVAILABLE_MODELS = get_available_models()
AVAILABLE_MODEL_LABELS = get_all_labels()
