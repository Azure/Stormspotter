import dash
import json
import time
import argparse
import dash_cytoscape as dcy
from pathlib import Path
from pprint import pprint
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from stormspotter.dash.layout.cytoscape import NODE_LAYOUTS
from stormspotter.dash.layout.ui import app_layout
from stormspotter.dash.core.context import DashParser
from stormspotter.dash.core.parsers import getNodeInfo, getEdgeInfo, checkDoubleClick

app = dash.Dash(__name__, assets_folder=Path("stormspotter/dash/assets").absolute())
app.config.suppress_callback_exceptions = True
app.layout = app_layout(app)
app.title = "Stormspotter"

#@app.callback(Output('db-content', 'children'),
#              [Input('db-interval', 'n_intervals')])
def displayDbInfo(intervals):
    event = dash.callback_context.triggered[0]
    if event['value'] == None:
        return

    counts = parser.dbSummary()
    print(counts.data())


@app.callback(Output('node-content-div', 'children'),
              [Input('cy', 'tapNodeData'), Input('cy', 'tapEdge'),
              Input('raw-switch', 'on')], [State('cy', 'selectedNodeData'),
              State('cy', 'selectedEdgeData')])
def displayTapNodeData(tapNode, tapEdge, raw, selectedNode, selectedEdge):
    event = dash.callback_context.triggered[0]

    if event['value'] == None:
        raise PreventUpdate

    trig = event['prop_id'].split(".")[1]
    if trig == "tapNodeData":
        return getNodeInfo(tapNode, raw)
    elif trig == "tapEdge":
        return getEdgeInfo(tapEdge, raw)
    elif trig == "on":
        if selectedNode:
            return getNodeInfo(selectedNode[0], raw)
        elif selectedEdge:
            return getEdgeInfo(selectedEdge[0], raw)

@app.callback(Output('data-tabs', 'value'),
              [Input('node-content-div', 'children')])
def swapToNodeTab(data):
    event = dash.callback_context.triggered[0]
    if event['value'] == None:
        raise PreventUpdate
    return "node-data"

@app.callback(Output('cy', 'layout'),
              [Input('layout-button', 'n_clicks')],
              [State('cy', 'layout')])
def updateLayout(clicks, current):
    if clicks is None:
        raise PreventUpdate
    return next(NODE_LAYOUTS)

@app.callback(Output('filter-name', 'options'),
              [Input('data-tabs', 'value'), Input('filter-td', 'n_clicks')])
def updateLabels(tab, filtertd):
    event = dash.callback_context.triggered[0]
    if event["value"] == "node-data" or event["prop_id"] == "filter-td.n_clicks":
        labels = parser.neo.labels
        return [{'label' : "ANY", 'value': "Any"}] + [{'label': lbl, 'value': lbl} for lbl in labels]
    else:
        raise PreventUpdate

@app.callback(Output('filter-key', 'options'),
              [Input('filter-name', 'value')])
def updateKeys(label):
    event = dash.callback_context.triggered[0]
    if event['value'] == None:
        raise PreventUpdate

    if label != "Any":
        keyList = next(filter(lambda k: k["label"] == label, parser.neo.keys))
        return [{'label' : "", 'value': "None"}] + [{'label': key, 'value': key} for key in sorted(keyList["props"])]
    else:
        keys = sorted(set(key for keyList in parser.neo.keys for key in keyList["props"]))
        return [{'label' : "", 'value': "NONE"}] + [{'label': key, 'value': key} for key in keys]

@app.callback(Output('layout-tt', 'children'),
              [Input('cy', 'layout')])
def updateLayoutTT(layout):
    return f"Graph Layout\n(Current: {layout['name']})"

@app.callback(Output('cypher-div', 'style'),
              [Input('cypher-switch', 'on')])
def cypher_on(on):
    event = dash.callback_context.triggered[0]
    if event['value'] == None:
        raise PreventUpdate

    if on:
        return {'display': 'block'}
    return {'display': 'none'}

@app.callback(Output('cy', 'elements'),
              [Input('cypher-input', 'n_submit'),  Input('filter-value', 'n_submit'),
               Input('filter-button', 'n_clicks'), Input('cy', 'tapNodeData'),
               Input('cy', 'tapEdgeData')],
              [State('cypher-input', 'value'), State('filter-value', 'value'),
               State('filter-name', 'value'), State('filter-key', 'value'), State('cy', 'tapNode'),
               State('cy', 'elements')])
def cypher_query(cyenter, filenter, filbutton, tapNode, tapEdge, query, filvalue, filname, filkey, nodedata, elements):
    event = dash.callback_context.triggered[0]
    filtrigs = ["filter-value.n_submit", "filter-button.n_clicks"]
    if event['value'] == None:
        raise PreventUpdate
    prop = event["prop_id"]
    if prop == "cy.tapNodeData":
        edge_ids = [edge["id"] for edge in nodedata["edgesData"]]
        for ele in elements:
            if ele["data"]["id"] in edge_ids:
                if tapNode["id"] == ele["data"]["source"]:
                    ele.update({"classes": "followingEdge"})
                else:
                    ele.update({"classes": "followerEdge"})
            else:
                ele.update({"classes": ""})
        return elements

    elif prop == "cy.tapEdgeData":
        for ele in elements:
            if ele["data"]["id"] == tapEdge["id"]:
                ele.update({"classes": "followingEdge"})
            else:
                ele.update({"classes": ""})
        return elements

    elif prop == "cypher-input.n_submit" and query:
        result = parser.getQuery(query=query)
        return result
    
    elif prop in filtrigs:
        return parser.getQuery(fquery=[filname, filkey, filvalue])

    return []

if __name__ == "__main__":
    dcy.load_extra_layouts()
    parser = argparse.ArgumentParser(description='Stormspotter')
    parser.add_argument("--dbuser", "-dbu", required=True,
                        help='Username for neo4j', default="neo4j")
    parser.add_argument("--dbpass", "-dbp", required=True,
                        help='Password for neo4j')
    parser.add_argument("--db",
                        help='Url of database', default="bolt://localhost:7687")

    args = parser.parse_args()
    # parser = DashParser("neo4j", "password")
    parser = DashParser(args.dbuser, args.dbpass, args.db)
    app.run_server(debug=False, threaded=True)