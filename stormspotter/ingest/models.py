import json
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, validator
from pydantic.main import create_model
from pydantic.fields import ModelField
from rich import print


class DynamicObject:
    def __init__(self, d: dict) -> None:
        self.__dict__.update(d)

    def __repr__(self) -> str:
        return str(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "DynamicObject":
        return json.loads(json.dumps(d, default={}), object_hook=DynamicObject)


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

    # A. Ignore all extra fields
    # B. Encode DynamicObject by getting the __dict__
    class Config:
        extra = "ignore"
        json_encoders = {DynamicObject: lambda v: v.__dict__}

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

    # https://github.com/samuelcolvin/pydantic/issues/1937
    def add_fields(self, **field_definitions: Any):
        """Dynamically add fields to model"""

        new_fields: Dict[str, ModelField] = {}
        new_annotations: Dict[str, Optional[type]] = {}

        for f_name, f_def in field_definitions.items():
            if isinstance(f_def, tuple):
                try:
                    f_annotation, f_value = f_def
                except ValueError as e:
                    raise Exception(
                        "field definitions should either be a tuple of (<type>, <default>) or just a "
                        "default value, unfortunately this means tuples as "
                        "default values are not allowed"
                    ) from e
            else:
                f_annotation, f_value = None, f_def

            if f_annotation:
                new_annotations[f_name] = f_annotation

            new_fields[f_name] = ModelField.infer(
                name=f_name,
                value=f_value,
                annotation=f_annotation,
                class_validators=None,
                config=self.__config__,
            )

        self.__fields__.update(new_fields)
        self.__annotations__.update(new_annotations)

    def node(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"properties"})


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
    __xfields__: ClassVar[List[str]] = None

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
                field_name = field.split(".")[-1]
                self.add_fields(
                    **{f"{field_name}": getattr(self.properties, field_name, None)}
                )

    @property
    def subscription(self) -> str:
        """Get the subscription from the id"""
        return self.id.split("/")[2] if "subscriptions" in self.id else None

    @property
    def resourcegroup(self) -> str:
        """Get the resource group from the id"""
        return self.id.split("/providers")[0] if "providers" in self.id else None

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


class ResourceGroup(ARMResource):
    __arm_type__ = "microsoft.resources/resourcegroups"


class KeyVault(ARMResource):
    __arm_type__ = "microsoft.keyvault/vaults"
    __xfields__ = [
        "enableSoftDelete",
        "softDeleteRetentionInDays",
        "enableRbacAuthorization",
        "enablePurgeProtection",
        "vaultUri",
    ]


class StorageAccount(ARMResource):
    __arm_type__ = "microsoft.storage/storageaccounts"
    __xfields__ = ["provisioningState"]


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
