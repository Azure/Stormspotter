<p align="center">
    <img src="docs/stormspotter.png" /><br>
    <img src="https://img.shields.io/badge/Version-1.0.0b-red" />
    <img src="https://img.shields.io/badge/python-3.8-success" />
</p>

Stormspotter creates an “attack graph” of the resources in an Azure subscription. It enables red teams and pentesters to visualize the attack surface and pivot opportunities within a tenant, and supercharges your defenders to quickly orient and prioritize incident response work.

It needs reader access to the subscription you wish to import and/or Directory.Read access to the Azure AD tenants.

---

# Installation

First things first:

`git clone https://github.com/Azure/Stormspotter`

## With Docker

Most users may find it easier to install Stormspotter via Docker.

`docker-compose up`

The `docker-compose` file will create two containers:

- Stormspotter
- Neo4j v4

By default, the Stormspotter container will expose the UI on port 9091. The neo4j container will expose neo4j on ports 7474 (HTTP), and 7687 (Bolt). Default configuration of Neo4j does not have SSL enabled, therefore you may initially interact directly with the neo4j interface on port 7474.

## Without Docker

If you choose to run Stormspotter without Docker, you must have Python 3.8 and npm installed.

### Backend

The backend handles parsing data into Neo4j is built with [FastAPI](https://fastapi.tiangolo.com/). If you don't plan on uploading new content for the database, you may not need to run the backend at all. The backend is configured to run on port 9090. You may change this by changing the port number on line 5 of [app.py](stormfront-backend/app.py). If you do, you must also change the port in the Q-Uploader component in the [DatabaseView Component](stormfront/src/components/DatabaseView.vue) so that the uploads from the frontend get sent to the correct port where the backend resides.

```
cd dist
python3 ssbackend.pyz
```

### Web App

The web app is developed using [Vue](https://vuejs.org/) and the [Quasar Framework](https://quasar.dev/). The single-page app (SPA) has been built for you and resides in `dist/spa`. To serve this directory:

```
npm install -g @quasar/cli
cd dist/spa
quasar serve -p 9091 --history
```

You can then visit http://localhost:9091 in your browser.

# Running Stormspotter

### Stormcollector

Stormcollector is the portion of Stormspotter that allows you to enumerate the subscriptions the provided credentials have access to. The **_RECOMMENDED_** way to use Stormcollector is to run the `sscollector.pyz` package. This PYZ has been created with [Shiv](https://github.com/linkedin/shiv) and comes with all the packages already zipped up! The dependencies will extract themselves to a `.shiv` folder in the user's home directory.

```
cd dist
python3 sscollector.pyz -h
```

If you don't want to use the provided package, you may install the required packages in `pyproject.toml` with `pip`. It's highly recommended to install Stormcollector in a virtual environment to prevent package conflicts.

```
cd stormcollector
python3 -m pip install .
python3 ./sscollector.py
```

Current login types supported:

- Azure CLI (must use `az login` first)
- Service Principal Client ID/Secret

You can check out all of the options Stormcollector offers by using the `-h` switch as shown above. The most basic usages of Stormcollector are:

```
python3 sscollector.pyz cli
python3 sscollector.pyz spn -t <tenant> -c <clientID> -s <clientSecret>
```

Some interesting options include `--aad` and `--arm`, which offer the options to only enumerate Azure AD or Azure Resource Manager.

## Notes

- With Stormspotter currently in beta, not all resource types have been implemented. You may see labels with missing icons and/or simply display the "name" and "id" fields. Over time, more resources will be properly implemented.

# Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
