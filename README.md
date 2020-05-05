<p align="center">
    <img src="misc/stormspotter.png" /><br>
    <img src="https://img.shields.io/badge/Version-1.0.0a-red" />
    <img src="https://img.shields.io/badge/python-3.8-success" />
</p>

# Stormspotter

Stormspotter creates a neo4j graph view of your Azure subscription and assets as well as Azure AD tenants using public APIs. It needs reader access to the subscription you wish to import and/or Directory.Read access to the Azure AD tenants. 

---

## Getting Started

### Prerequisites

- Stormspotter is developed in Python 3.8.
- Install [Neo4j](https://neo4j.com/download/). Installation directions for your preferred operating system are located [here](https://neo4j.com/docs/operations-manual/current/installation/), although you may prefer the ease of a docker container:

```
docker run --name stormspotter -p7474:7474 -p7687:7687 -d --env NEO4J_AUTH=neo4j/[password] neo4j:latest
```
---
## Running Stormspotter
In order to avoid conflicting packages, it is highly recommended to run Stormspotter in a virtual environment.

1. Install the requirements

    - Via pip
    ```
    pipenv install stormspotter
    ```

    - From the repository   
    ```
    git clone https://github.com/Azure/Stormspotter
    cd Stormspotter
    pipenv install -e .
    ```

#### Providing credentials
Current login types supported: 

- Azure CLI (must use `az login` first)
- Service Principal Client ID/Secret

#### Gather and view resources

1. Run stormspotter to gather resource and object information
    ```
    stormspotter --cli
   ```

2. Run stormdash to launch dashboard
    ```
    stormdash -dbu <neo4j-user> -dbp <neo4j-pass>
    ```

3. During installation, a `.stormspotter` folder is created in the user's home directory. Place the results zip file into `~/.stormspotter/input` folder. You may also place the zip file into the folder before running `stormdash` and it will be processed when Stormspotter starts. When a file is successfully processed, it will be moved into `~/.stormspotter/processed`.
   
# Screenshots

![Screenshot1](misc/screenshot1.png)
![Screenshot2](misc/screenshot2.png)
![Screenshot3](misc/screenshot3.png)

# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
