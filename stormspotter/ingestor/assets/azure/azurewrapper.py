import json
import re
from itertools import chain
from concurrent.futures import ThreadPoolExecutor, wait, as_completed
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient
from msrestazure.azure_exceptions import CloudError
from stormspotter.ingestor.assets.azure import rbac
from stormspotter.ingestor.utils import Recorder
from stormspotter.ingestor.utils.resources import *

def _query_resource(asset_id, context, api_version="2018-02-14", version_blacklist=[]):
    try:
        return context.client.resources.get_by_id(asset_id, api_version, raw=True).response.json()
    except CloudError as ex:
        if "No registered resource provider found for location" in ex.message:
            version_blacklist.append(api_version)
            api_versions = re.search(
                "The supported api-versions are '(.*?),", ex.message
            ).groups()
            api_versions = list(filter(lambda v: v not in version_blacklist, api_versions))
            if api_versions:
                return _query_resource(asset_id, context, api_version=api_versions[0], version_blacklist=version_blacklist)

def _query_subscription(context, sub_id):
    resources = [sub_id]
    print(f"Querying for resources in subscription id {sub_id}")
    client = ResourceManagementClient(context.auth.resource_cred, sub_id)
    context.client = client
    for item in client.resources.list():
        type_name = item.type.lower()
        asset = _query_resource(item.id, context)
        resources.append(asset)
    return resources

def query_azure_subscriptions(context, sub_list=None):
    sub_list = get_sub_list(context, sub_list)

    rbac_list = []
    cert_list = []    
    tpe = ThreadPoolExecutor()
    futures = list(chain([tpe.submit(_query_subscription, context, sub_id) for sub_id in sub_list],
                         [tpe.submit(rbac.get_rbac_permissions, context, sub_id) for sub_id in sub_list],
                         [tpe.submit(rbac.get_management_certs, context, sub_id) for sub_id in sub_list]
                         ))

    for f in as_completed(futures):
        if f.result()[0] == "rbac":
            rbac_list += f.result()[1:]
        elif f.result()[0] == "certs":
            cert_list += f.result()[1:]
        else:
            Recorder.writestr(f"{f.result()[0]}.json", json.dumps(f.result()[1:], sort_keys=True))

    Recorder.writestr("rbac.json", json.dumps(rbac_list, sort_keys=True))
    Recorder.writestr("certs.json", json.dumps(cert_list, sort_keys=True))

def get_sub_list(context, sub_list=None):
    sub_client = SubscriptionClient(context.auth.resource_cred)
    tens = [ten for ten in sub_client.tenants.list()]
    ten_asset = {
        "tenantId": tens[0].tenant_id,
        "category": tens[0].tenant_category,
        "country": tens[0].country,
        "countryCode": tens[0].country_code,
        "name": tens[0].display_name,
        "domains": tens[0].domains,
        "subscriptions": []
    }
    subs = [sub for sub in sub_client.subscriptions.list()]
    if sub_list:
        subs = filter(lambda s: s.subscription_id in sub_list_filter, subs)
    sub_ids = [sub.subscription_id for sub in subs]
    for sub in subs:
        client = ResourceManagementClient(context.auth.resource_cred, sub.subscription_id)
        resource_groups = [rg for rg in client.resource_groups.list()]
        sub_asset = {
            "name": sub.display_name,
            "state": sub.state.value,
            "id": sub.id,
            "subscriptionId": sub.subscription_id,
            "managedBy": sub.managed_by_tenants,
            "tags": [[k,v] for k,v in sub.tags.items()] if isinstance(sub.tags, dict) else None,
            "resourceGroups": [{"id": rg.id, "name": rg.name, "location": rg.location, 
                                "type": rg.type, "managedBy": rg.managed_by, 
                                "tags": [[k,v] for k,v in sub.tags.items()] if isinstance(sub.tags, dict) else None} 
                              for rg in resource_groups]
        }
        if sub.subscription_policies.spending_limit:
            sub_asset["spendingLimit"] = sub.subscription_policies.spending_limit.value
        ten_asset["subscriptions"].append(sub_asset)
    Recorder.writestr("subdata.json", json.dumps([ten_asset], sort_keys=True))
    return sub_ids


def finalize(context):    
    pass
