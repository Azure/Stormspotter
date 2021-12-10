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

    AssociatedTo = auto()
    AttachedTo = auto()
    Authenticates = auto()
    ConnectedTo = auto()
    Contains = auto()
    Exposes = auto()
    HasAccessPolicies = auto()
    HasConfig = auto()
    HasRbac = auto()
    HasRole = auto()
    Is = auto()
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

    @validator("source", "target")
    def lower_id(cls, value: str):
        """Convert id to lowercase"""
        return value.lower()

    def toNeo(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"properties"})


class Node(BaseModel):
    """Base model for all nodes"""

    id: str
    _relationships: List[Relationship] = PrivateAttr(default_factory=list)

    # A. Ignore all extra fields
    # B. Encode DynamicObject by getting the __dict__
    # C. Allow for arbitrary types, like DynamicObject
    class Config:
        extra = "ignore"
        json_encoders = {DynamicObject: lambda v: v.__dict__}
        arbitrary_types_allowed = True

    @validator("id")
    def lower_id(cls, value: str):
        """Convert id to lowercase"""
        return value.lower()

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

    def toNeo(self) -> Dict[str, Any]:
        """Node representation safe for Neo4j"""
        return self.dict(exclude={"properties"})


####--- AAD RELATED MODELS ---###
class AADObject(Node):
    """Base Neo4JModel for AAD objects"""

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

    def toNeo(self) -> Dict[str, Any]:
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
    accountEnabled: Optional[bool]
    appDisplayName: Optional[str] = ...
    appId: str
    appOwnerOrganizationId: Optional[str] = ...
    owners: Optional[List[str]]
    publisherName: Optional[str] = ...
    servicePrincipalType: Optional[str]


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
    __xfields__: ClassVar[List[str]] = []
    __map_to_resourcegroup__: ClassVar[bool] = True
    __xdict__: Dict[str, Any] = PrivateAttr(default_factory=dict)

    location: Optional[str]
    name: Optional[str]
    properties: Optional[DynamicObject]
    kind: Optional[str]
    tags: Optional[List[str]]
    identity: Optional[Dict[str, Any]]

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # Grab the field from the properties and set it as it's own property

        if self.properties and self.__class__.__xfields__:
            for field in self.__class__.__xfields__:
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

        # If there's a managed identity, add it to relations
        # "None" here is a string, not a None object
        if self.identity and self.identity.get("type") != "None":
            msi = AADServicePrincipal(
                id=self.identity["principal_id"],
                displayName=self.name,
                appOwnerOrganizationId=self.identity["tenant_id"],
            )
            self._relationships.append(msi)
            self._relationships.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[0],
                    target=msi.id,
                    target_label=msi._labels()[0],
                    relation=RelationLabels.Is,
                )
            )
        else:
            self.identity = None

        # Check additional relationships for subclasses
        if additional_rels := self.__relationships__():
            self._relationships.extend(additional_rels)

    @property
    def subscription(self) -> str:
        """Get the subscription from the id"""
        return self.id.split("/resourcegroups")[0]

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
    def props_to_obj(cls, dict_value: dict):
        """Convert properties dictionary to dynamic object"""
        if isinstance(dict_value, DynamicObject):
            return dict_value

        return DynamicObject.from_dict(dict_value)

    def toNeo(self) -> Dict[str, Any]:
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
    managed_by_tenants: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

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

        for managed in self.managed_by_tenants:
            tenant = Tenant(**managed)
            relations.append(tenant)
            relations.append(
                Relationship(
                    source="/tenants/" + tenant.tenant_id,
                    source_label=Tenant._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.Manages,
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


class BotService(ARMResource):
    __arm_type__ = "microsoft.botservice/botServices"
    __xfields__ = [
        "displayName",
        "description",
        "endpoint",
        "msaAppId",
        "developerAppInsightKey",
        "enabledChannels",
    ]


class ClassicStorageAccount(ARMResource):
    __arm_type__ = "microsoft.classicstorage/storageaccounts"
    __xfields__ = ["creationTime", "endpoints"]


class ContainerGroup(ARMResource):
    __arm_type__ = "microsoft.containerinstance/containergroups"
    __xfields__ = ["osType"]


class ContainerRegistry(ARMResource):
    __arm_type__ = "microsoft.containerregistry/registries"
    __xfields__ = [
        "loginServer",
        "adminUserEnabled",
        "publicNetworkAccess",
        "anonymousPullEnabled",
    ]


class ContainerRegistryWebhook(ARMResource):
    __arm_type__ = "microsoft.containerregistry/registries/webhook"
    __xfields__ = ["scope", "actions"]


class Dashboard(ARMResource):
    __arm_type__ = "microsoft.portal/dashboards"


class DatabaseAccount(ARMResource):
    __arm_type__ = "microsoft.documentdb/databaseaccounts"
    __xfields__ = [
        "documentEndpoint",
        "publicNetworkAccess",
        "EnabledApiTypes",
        "disableKeyBasedMetadataWriteAccess",
    ]


class DataLakeStoreAccount(ARMResource):
    __arm_type__ = "microsoft.datalakestore/accounts"
    __xfields__ = [
        "firewallState",
        "firewallAllowAzureIps",
        "firewallAllowDataLakeAnalytics",
        "endpoint",
        "creationTime",
        "lastModifiedTime",
    ]


class Disk(ARMResource):
    __arm_type__ = "microsoft.compute/disks"
    __xfields__ = [
        "osType",
        "hyperVGeneration",
        "diskSizeGB",
        "networkAccessPolicy",
        "publicNetworkAccess",
        "diskState",
        "timeCreated",
    ]

    managed_by: Optional[str] = ...

    def __relationships__(self) -> List[Relationship]:
        relations = []
        if self.managed_by:
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=Disk._labels()[0],
                    target=self.managed_by,
                    target_label=ARMResource._labels()[0],
                    relation=RelationLabels.AttachedTo,
                )
            )
        return relations


class InsightsActionGroup(ARMResource):
    __arm_type__ = "microsoft.insights/actiongroups"
    __xfields__ = "groupShortName"


class InsightsComponent(ARMResource):
    __arm_type__ = "microsoft.insights/components"
    __xfields__ = [
        "ApplicationId",
        "AppId",
        "Request_Source",
        "Instrumentationkey",
        "ConnectionString",
        "RetentionInDays",
        "publicNetworkAccessForIngestion",
        "publicNetworkAccessForQuery",
        "tenantId",
    ]


class InsightsWorkbook(ARMResource):
    __arm_type__ = "microsoft.insights/workbooks"
    __xfields__ = ["displayName", "version", "userId", "sourceId"]


class IpConfiguration(ARMResource):
    __arm_type__ = "microsoft.network/networkinterfaces/ipconfigurations"
    __xfields__ = [
        "privateIPAddress",
        "privateIPAllocationMethod",
        "primary",
        "privateIPAddressVersion",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        if publicip_id := self.properties.publicIpAddress.id:
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[1],
                    target=publicip_id,
                    target_label=PublicIPAddress._labels()[0],
                    relation=RelationLabels.Exposes,
                )
            )

        if subnet_id := self.properties.subnet.id:
            relations.append(
                Relationship(
                    source=subnet_id,
                    source_label=Subnet._labels()[1],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.HasConfig,
                )
            )
        return relations


class LogicWorkflow(ARMResource):
    __arm_type__ = "microsoft.logic/workflows"
    __xfields__ = ["state, createdTime", "changedTime", "accessEndpoint", "version"]


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


class NetworkInterface(ARMResource):
    __arm_type__ = "microsoft.network/networkinterfaces"
    __xfields__ = [
        "macAddress",
        "enableIPForwarding",
        "primary",
        "dnsSettings.dnsServers",
        "dnsSettings.appliedDnsServers" "dnsSettings.internalDomainNameSuffix",
        "nicType",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        if vm_id := self.properties.virtualMachine.id:
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[0],
                    target=vm_id,
                    target_label=VirtualMachine._labels()[0],
                    relation=RelationLabels.AttachedTo,
                )
            )

        if nsg_id := self.properties.networkSecurityGroup.id:
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[0],
                    target=nsg_id,
                    target_label=NetworkSecurityGroup._labels()[0],
                    relation=RelationLabels.AssociatedTo,
                )
            )
        return relations


class NetworkSecurityGroup(ARMResource):
    __arm_type__ = "microsoft.network/networksecuritygroups"

    def __relationships__(self) -> List[Relationship]:
        relations = []
        for interface in self.properties.networkInterfaces:
            relations.append(
                Relationship(
                    source=interface.id,
                    source_label=NetworkInterface._labels()[0],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.AssociatedTo,
                )
            )
        return relations


class NetworkWatcher(ARMResource):
    __arm_type__ = "microsoft.network/networkwatchers"
    __xfields__ = ["runningOperationIds"]


class PublicIPAddress(ARMResource):
    __arm_type__ = "microsoft.network/publicipaddresses"
    __xfields__ = [
        "ipAddress",
        "dnsSettings.fqdn",
        "publicIPAddressVersion",
        "publicIPAllocationMethod",
        "idleTimeoutInMinutes",
        "ipTags",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        if ipconfig_id := self.properties.ipConfiguration.id:
            relations.append(
                Relationship(
                    source=ipconfig_id,
                    source_label=IpConfiguration._labels()[1],
                    target=self.id,
                    target_label=self._labels()[0],
                    relation=RelationLabels.Exposes,
                )
            )
        return relations


class PurviewAccount(ARMResource):
    __arm_type__ = "microsoft.purview/accounts"
    __xfields__ = [
        "friendlyName",
        "createdBy",
        "createdAt",
        "managedResourceGroupName",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        relations.append(ResourceGroup(id=self.managedResourceGroupName))
        relations.append(
            Relationship(
                source=self.id,
                source_label=self._labels()[1],
                target=self.properties.managedResources.resourceGroup,
                target_label=ResourceGroup._labels()[0],
                relation=RelationLabels.Exposes,
            )
        )
        return relations


class Redis(ARMResource):
    __arm_type__ = "microsoft.cache/redis"
    __xfields__ = ["redisVersion", "publicNetworkAccess", "hostName", "port", "sslPort"]


class StaticSite(ARMResource):
    __arm_type__ = "microsoft.web/staticsites"
    __xfields__ = [
        "defaultHostname",
        "repositoryUrl",
        "branch",
        "customDomains",
        "provider",
    ]


class Site(ARMResource):
    __arm_type__ = "microsoft.web/sites"
    __xfields__ = [
        "enabled",
        "state",
        "hostnames",
        "enabledHostNames",
        "repositorySiteName",
    ]


class SqlServer(ARMResource):
    __arm_type__ = "microsoft.sql/servers"
    __xfields__ = [
        "administratorLogin",
        "state",
        "fullyQualifiedDomainName",
        "publicNetworkAccess",
        "restrictOutboundNetworkAccess",
    ]


class SqlServerDatabase(ARMResource):
    __arm_type__ = "microsoft.sql/servers/databases"
    __xfields__ = ["status", "creationDate", "earliestRestoreDate"]


class Solution(ARMResource):
    __arm_type__ = "microsoft.operationsmanagement/solutions"
    __xfields__ = ["creationTime", "lastModifiedTime", "containedResources"]


class StorageAccount(ARMResource):
    __arm_type__ = "microsoft.storage/storageaccounts"
    __xfields__ = [
        "accessTier",
        "creationTime",
        "supportsHttpsTrafficOnly",
        "networkAcls.bypass",
        "networkAcls.defaultAction",
    ]


class Subnet(ARMResource):
    __arm_type__ = "microsoft.network/virtualnetworks/subnets"
    __xfields__ = [
        "addressPrefix",
        "privateEndpointNetworkPolicies",
        "privateLinkServiceNetworkPolicies",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []
        for ipconfig in self.properties.ipConfigurations:
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[0],
                    target=ipconfig.id,
                    target_label=IpConfiguration._labels()[0],
                    relation=RelationLabels.HasConfig,
                )
            )


class UserAssignedIdentity(ARMResource):
    __arm_type__ = "microsoft.managedidentity/userassignedidentities"
    __xfields__ = ["tenantId", "principalId", "clientId"]

    def __relationships__(self) -> List[Relationship]:
        return [
            Relationship(
                source=self.id,
                source_label=self._labels()[0],
                target=self.principalId,
                target_label=AADServicePrincipal._labels()[0],
                relation=RelationLabels.Is,
            )
        ]


class VirtualMachine(ARMResource):
    __arm_type__ = "microsoft.compute/virtualmachines"
    __xfields__ = [
        "osProfile.computerName",
        "osProfile.adminUsername",
        "osProfile.allowExtensionOperations",
        "hardwareProfile.vmSize",
        "storageProfile.imageReference.publisher",
        "storageProfile.imageReference.offer",
        "storageProfile.imageReference.sku",
        "storageProfile.imageReference.exactVersion",
    ]

    def __relationships__(self) -> List[Relationship]:
        relations = []

        for interface in self.properties.networkProfile.networkInterfaces:
            relations.append(
                Relationship(
                    source=interface.id,
                    source_label=NetworkInterface._labels()[0],
                    target=self.id,
                    target_label=VirtualMachine._labels()[0],
                    relation=RelationLabels.AttachedTo,
                )
            )

        osdisk_id = self.properties.storageProfile.osDisk.managedDisk.id
        relations.append(
            Relationship(
                source=osdisk_id,
                source_label=Disk._labels()[0],
                target=self.id,
                target_label=self._labels()[0],
                relation=RelationLabels.AttachedTo,
            )
        )
        return relations


class VirtualNetwork(ARMResource):
    __arm_type__ = "microsoft.network/virtualnetworks"
    __xfields__ = ["addressSpace.addressPrefixes", "enableDdosProtection"]

    def __relationships__(self) -> List[Relationship]:
        relations = []

        for subnet in self.properties.subnets:
            subnet_node = Subnet.parse_obj(subnet.__dict__)
            relations.append(subnet_node)
            relations.append(
                Relationship(
                    source=self.id,
                    source_label=self._labels()[0],
                    target=subnet_node.id,
                    target_label=subnet_node._labels()[0],
                    relation=RelationLabels.Contains,
                )
            )
        return relations


class VMExtension(ARMResource):
    __arm_type__ = "microsoft.compute/virtualmachines/extensions"
    __xfields__ = [
        "autoUpgradeMinorVersion",
        "publisher",
        "type",
        "typeHandlerVersion",
        "settings",
    ]


class Workspace(ARMResource):
    __arm_type__ = "microsoft.operationalinsights/workspaces"
    __xfields__ = [
        "source",
        "customerId",
        "retentionInDays",
        "createdDate",
        "modifiedDate",
    ]


def get_available_models() -> Dict[str, Node]:
    """Returns models available for Neo4j ingestion"""

    # AAD models need to use qualname or else you get ModelMetaclass back.
    aad_models = {qualname_base(c): c for c in AADObject.__subclasses__()}
    arm_models = {c.__arm_type__: c for c in ARMResource.__subclasses__()}
    return aad_models | arm_models


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
