PRESET_QUERIES = {
    "Find all with Admin or Permissions over Key Vaults":
        "MATCH (n)-[r:Admin|:Permissions]-(p:KeyVault) RETURN n,r,p",
    "Find all Azure AD objects with Admin privileges over a resource":
        "MATCH (n)-[r:Admin]-(p) RETURN n,r,p"
}