import json
import time
import dash_bootstrap_components as dbc
import dash_html_components as html
from pprint import pformat, pprint

NODE_CLICK_TIME = time.time()

def checkDoubleClick():
    global NODE_CLICK_TIME

    t = time.time()
    print(NODE_CLICK_TIME, t, t - NODE_CLICK_TIME)
    if t - NODE_CLICK_TIME <= 1:
        NODE_CLICK_TIME = t
        return True
    NODE_CLICK_TIME = t
    return False

def makeDbSummary(neo):
    title = html.P("Database Stats", className="dbtitle")
    hr = html.Hr(style={'width': "100%"})

    body = []
    body.append(html.Tr([html.Td("Database", className="rowname"), html.Td(neo.server, className="rowvalue")]))
    body.append(html.Tr([html.Td("User", className="rowname"), html.Td(neo.user, className="rowvalue")]))

    counts = neo.dbSummary().data()
    for res in counts:
        if len(res['labels']) > 1:
            res['labels'].remove('AADObject') if 'AADObject' in res['labels'] else res['labels'].remove('AzureResource')
        res["labels"] = "".join(res["labels"])
    sortedCounts = sorted(counts, key=lambda r: r["labels"])

    stats = []
    for a,b in zip(*[iter(sortedCounts)]*2):
        stats.append(html.Tr([html.Td(a.get("labels"), className="rowname"), 
                             html.Td(a.get("count"), className="rowvalue"),
                             html.Td(b.get("labels"), className="rowname"), 
                             html.Td(b.get("count"), className="rowvalue")]))
    return [title, dbc.Table(body), hr, dbc.Table(stats)]

def getNodeInfo(node, raw):
    if raw:
        return html.Pre(json.dumps(json.loads(node["raw"]), indent=4)) 
    else:
        try:
            return NODE_MAPPINGS[node["type"]](node)
        except KeyError:
        #return html.Pre(node["raw"])   
            name = makeMainBody(node, ["name"])
            _type = makeMainBody(json.loads(node["raw"]), ["type"])
            return dbc.Table(name + _type)

def getEdgeInfo(edgeData, raw):
    try:
        perms = edgeData["data"]["properties"]
        nodes = makeMainBody(edgeData["data"], ["sourceName", "label", "targetName"])
    except KeyError:
        perms = edgeData["properties"]
        nodes = makeMainBody(edgeData, ["sourceName", "label", "targetName"])


    if raw:
        return html.Pre(json.dumps(perms, indent=4))

    # props = [html.Tr([html.Td(k, className="rowname"),
    #                   html.Td(v, className="rowvalue")])
    #                   for k,v in perms.items()]
    props = makeMainBody(perms, perms.keys())
    return dbc.Table(nodes + props)

def makeMainBody(node, fields):
    body = []
    for f in fields:
        value = node.get(f)
        if value in ['None', None] or not value:
            value = ""
        elif isinstance(value, list):
            value = "\n".join(value)
        elif isinstance(value, bool):
            value = str(value)
        body.append(html.Tr([html.Td(f, className="rowname"), html.Td(value, className="rowvalue")]))
    return body

def parseAADServicePrincipal(node):
    fields = ["name",
              "type",
              "objectId",
              "accountEnabled",
              "appId",
              "homepage",
              "appOwnerTenantId"]
    
    body = makeMainBody(node, fields)
    additional = [html.Tr([html.Td("keyCredentialCount", className="rowname"), 
                           html.Td(node["keyCredentialCount"], className="rowvalue")])]

    return dbc.Table(body + additional)

def parseAADUser(node):
    fields = ["name",
              "type",
              "objectId",
              "accountEnabled",
              "dirSyncEnabled",
              "userPrincipalName",
              "lastPasswordChangeDateTime"]

    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseAADGroup(node):
    fields = ["name",
              "type",
              "objectId",
              "description",
              "mail",
              "dirSyncEnabled",
              "securityEnabled",
              "lastPasswordChangeDateTime"]

    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseAADApplication(node):
    fields = ["name",
              "type",
              "objectId", 
              "appId", 
              "homepage", 
              "keyCredentialsCount",
              "passwordCredentialsCount", 
              "publisherDomain"]

    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseIpConfiguration(node):
    fields = ["name",
              "type",
              "primary",
              "privateIPAddress",
              "privateIPAllocationMethod"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parsePublicIp(node):
    fields = ["name",
              "type",
              "publicIPAllocationMethod",
              "fqdn",
              "ipAddress"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseKeyVault(node):
    fields = ["name",
              "type",
              "vaultUri",
              "enableRbacAuthorization",
              "enableSoftDelete",
              "softDeleteRetentionInDays",
              "enabledForDeployment",
              "enabledForDiskEncryption",
              "enabledForTemplateDeployment",
              "accessPolicyCount"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseNetworkInterface(node):
    fields = ["name",
              "type",
              "macAddress",
              "ipForwarding",
              "ipConfigurationCount"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseNetworkSecurityGroup(node):
    fields = ["name",
              "type",
              "ruleCount"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseResourceGroup(node):
    fields = ["name",
              "type",
              "location",
              "managedBy",
              "tags"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseRule(node):
    fields = ["name",
              "type",
              "description",
              "direction",
              "priority",
              "protocol",
              "sourceAddressPrefix",
              "sourcePortRange",
              "destionationAddressPrefix",
              "destinationPortRange"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseStorageAccount(node):
    fields = ["name",
              "type",
              "kind",
              "accessTier",
              "location",
              "supportsHttpTrafficOnly"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseSubscription(node):
    fields = ["name",
              "type",
              "state",
              "resourceGroupCount",
              "spendingLimit"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseTenant(node):
    fields = ["name",
              "type",
              "tenantId",
              "category",
              "country",
              "countryCode",
              "domains",
              "subscriptionCount",
              "tags"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseVirtualNetwork(node):
    fields = ["name",
              "type",
              "subnet"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

def parseWebsite(node):
    fields = ["name",
              "type",
              "kind",
              "enableRbacAuthorization",
              "enableSoftDelete",
              "softDeleteRetentionInDays",
              "enabledForDeployment",
              "enabledForDiskEncryption",
              "enabledForTemplateDeployment",
              "accessPolicyCount"]
    
    body = makeMainBody(node, fields)
    return dbc.Table(body)

NODE_MAPPINGS = {
        "AADServicePrincipal": parseAADServicePrincipal,
        "AADApplication": parseAADApplication,
        "AADUser": parseAADUser,
        "AADGroup": parseAADGroup,
        "IpConfiguration": parseIpConfiguration, 
        "KeyVault": parseKeyVault,
        "NetworkInterface": parseNetworkInterface,
        "NetworkSecurityGroup": parseNetworkSecurityGroup,
        "PublicIp": parsePublicIp,
        "ResourceGroup": parseResourceGroup,
        "Rule": parseRule,
        "StorageAccount": parseStorageAccount,
        "Tenant": parseTenant,
        "Subscription": parseSubscription,
        "VirtualNetwork": parseVirtualNetwork
}