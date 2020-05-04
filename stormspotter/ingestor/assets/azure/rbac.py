import requests
import re
import xml
from azure.mgmt.authorization import AuthorizationManagementClient
from stormspotter.ingestor.utils.resources import *
from stormspotter.ingestor.utils import SSC as context


ROLE_MAPPINGS = [
    {
        "name": "STORAGEADMIN",
        "permission": "Microsoft.Storage/storageAccounts/listKeys/action"
    }, {
        "name": "ARMADMIN",
        "permission": 'Microsoft.Authorization/roleAssignments/write'
    }, {
        "name": "VMADMIN",
        "permission": 'Microsoft.Compute/virtualMachines/extensions/write'
    }, {
        "name": "WEBADMIN",
        "permission": "Microsoft.Web/sites/Write"
    }, {
        "name": "KVADMIN",
        "permission": "Microsoft.KeyVault/vaults/write"
    }]


def _test_action_list(requested_action, permission_list):
    """ Determine if the requested action is allowed with a list of permissions """
    for permission in permission_list:
        if _test_action(requested_action, permission):
            return True
    return False


def _test_action(requested_action, permission):
    """ Determine if the requested action falls within a permission """
    permission = permission.replace("*", ".*")
    match = re.match(permission.lower(), requested_action.lower())
    return match is not None


def _test_action_json(requested_action, roles_json):
    """ Determine if the requested action is allowed within the permission json """
    if roles_json:
        if not _test_action_list(requested_action,
                                 roles_json[0]["notActions"]):
            if _test_action_list(requested_action, roles_json[0]["actions"]):
                return True
    return False


def _map_admin_type(sub_id, assignment_id, principal, scope, role_id,
                    role_name, permissions):
    """create relationship in database based off of allowed actions by aadobject"""
    obj_list = []
    for mapping in ROLE_MAPPINGS:
        requested_action = mapping["permission"]
        admin_type = mapping["name"]
        is_admin = _test_action_json(requested_action, permissions)
        if (is_admin):
            rel_props = {
                "role": role_id,
                "assignment": assignment_id,
                "scope": scope,
                "name": role_name
            }
            obj_list.append({"objectId": principal, "subscriptionId": sub_id,
                             "admintype": admin_type, "roleInfo": rel_props})
    return obj_list


def _get_permissions(cred, role_id):
    """get allowed actions for aadobject by calling ARM"""
    ARM_ENDPOINT = context.cloudContext.cloud.endpoints.resource_manager
    url = ARM_ENDPOINT + role_id + '?api-version=2018-01-01-preview'
    session = cred.signed_session()
    headers = session.headers
    r = requests.get(url, headers=headers)
    roles_json = r.json()
    if (roles_json):
        role_type = roles_json["properties"]["roleName"]
        permissions = roles_json["properties"]["permissions"]
        return role_type, permissions


def get_rbac_permissions(context, sub_id):
    print(f"Getting rbac permissions for subscription: {sub_id}")
    auth_client = AuthorizationManagementClient(
        context.auth.resource_cred, sub_id)
    rbacs = ["rbac"]

    for role in auth_client.role_assignments.list():
        scope = role.scope
        principal = role.principal_id
        assignment_id = role.id
        role_id = role.role_definition_id
        #role_id = f'/subscriptions/{sub_id}/providers/Microsoft.Authorization/roleAssignments/{role.name}'
        role_type, permissions = _get_permissions(
            context.auth.resource_cred, role_id)
        # querying for assignment id will give type of AADobject
        rbacs += (_map_admin_type(sub_id, assignment_id, principal, scope, role_id,
                        role_type, permissions))
    
    print(f"Finished management certs for subscription: {sub_id}")
    return rbacs

def get_management_certs(context, sub_id):
    print(f"Getting management certs for subscription: {sub_id}")
    MGMT_RES = context.cloudContext.cloud.endpoints.management
    cred = context.auth.resource_cred
    sess = cred.signed_session()
    XMS_VERSION = '2012-03-01'
    url = MGMT_RES + sub_id + '/certificates'
    cert_list = ["certs"]
    try:
        r = sess.get(url, headers={'x-ms-version': XMS_VERSION})
        # Parse the XML to pull out the thumbprint and creation date.
        d = xml.dom.minidom.parseString(str(r.text))
        for cert in d.getElementsByTagName('SubscriptionCertificate'):
            cert_asset = {
                "subscriptionId": sub_id,
                "thumbprint": cert.getElementsByTagName('SubscriptionCertificateThumbprint')[0].firstChild.nodeValue,
                "created": cert.getElementsByTagName('Created')[0].firstChild.nodeValue
            }
            cert_list += cert_asset
    
    except Exception:
        print (f"user or service principal does not have coadministrator access to subscription {sub_id} to access management certs.")

    print(f"Finished management certs for subscription: {sub_id}")
    return cert_list
    #for cert in cert_list:
        #context.neo4j.insert_asset(cert, CERTIFICATE_NODE_LABEL, cert["thumbprint"])
        #context.neo4j.create_relationship(cert["thumbprint"], CERTIFICATE_NODE_LABEL, sub_id, SUBSCRIPTION_NODE_LABEL, CERT_TO_ASSET)
