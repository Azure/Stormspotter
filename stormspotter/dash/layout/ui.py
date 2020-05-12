import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import dash_daq as daq
from .cytoscape import cyto
from ..core.queries import PRESET_QUERIES

def app_layout(app):
    return html.Div(className="container", children=[
            dcc.Store(id="local-store", storage_type="local"),
            dcc.Interval(id="db-interval", interval=5000, n_intervals=0),
            html.Div(className="pageDiv", children=[
            cyto]),

            #Legend - bottom left
            html.Div(id='icon-div', className='legend', children=[
                html.Div(id='legend-div', className='legend', children=[
                    html.Img(id="layout-button", src=app.get_asset_url("graph.png"), className="icon"),
                    # html.Img(id="settings-button", src=app.get_asset_url("settings.png"), className="icon"),
                    daq.BooleanSwitch(id="cypher-switch", label="QUERY", vertical=True,
                                    color="#0983af", labelPosition="bottom"),
                    dbc.Tooltip("Graph Layout\n(Current: cose-bilkent)", id="layout-tt", 
                                target="layout-button", placement="right", className="tooltip"),
                    # dbc.Tooltip("Settings", id="settings-tt", target="settings-button", 
                    #            placement="right", className="tooltip")
                ]),
                html.Div(id='cypher-div', className='cypher', style={'display': 'none'}, children=[
                    dbc.Input(id="cypher-input", debounce=True,
                            className="cypher", placeholder="Enter Raw Query",
                            value="MATCH (n) RETURN n LIMIT 50"),
                ]),
            ]),
            #Tabs - upper right
            html.Div([
                dcc.Tabs(id='data-tabs', 
                value='node-data',
                parent_className='custom-tabs', 
                className='custom-tabs-container', children=[
                    dcc.Tab(label="Database", value='db-info', className='custom-tab', children=[
                        html.Div(id='db-content-div', children=[
                            html.Pre(id='db-content', className="dbinfocontent"),
                            dcc.ConfirmDialogProvider(id='deletedb-provider', message='Are you sure you want to delete the database?', children=[
                                html.Button('Delete DB', className="bgbutton")   
                        ]),
                            html.Div(id="hiddendb-div")
                    ])]),
                    dcc.Tab(label="Node/Edge Info", value="node-data", className='custom-tab', children=[
                        html.Div(id='filter-search-div', className='filtersearch',children=[
                            html.Table(id='filter-table', className='filtertable', children=[
                                html.Tr(className="tablerows", children=[
                                    html.Td(id="filter-td", className="filtername", children=[
                                        dcc.Dropdown(id='filter-name', className="filtername", clearable=False, 
                                                     options=[])
                                    ]),
                                ]),
                                html.Tr(className="tablerows", children=[
                                    html.Td(className="filtername", children=[
                                        dcc.Dropdown(id='filter-key',clearable=False)
                                    ]),
                                    html.Td(children=dbc.Input(id='filter-value', placeholder="Search", 
                                                                                        className="filtervalue", debounce=True)),
                                    html.Td(children=html.Button(html.Img(id="filter-button", src=app.get_asset_url("filter.png"), 
                                                                 className="icon"),
                                                        className='filterbutton'))

                                ])
                            ]),
                        html.Div(id='node-content-div', className="nodeinfocontent", children=[
                                #html.Pre(id='raw-data', className="nodeinfocontent"),
                        ]),
                        daq.BooleanSwitch(id='raw-switch', label="Raw Data", color="#770f00",
                                          labelPosition="bottom", on=False, className="bgbutton")
                    ])]),
                    dcc.Tab(label="Queries", value="presets", className='custom-tab', children=[
                        html.Div(id='queries-content-div', children=[
                            html.Pre(id='queries-content', className="dbinfocontent", 
                            children=[html.Pre([html.P(k,className="rowname", style={'padding':"0", 'margin':"0"}),
                                                html.P(v, className="rowvalue", style={'padding':"0", 'margin':"0"}),]) 
                                                for k,v in PRESET_QUERIES.items()])
                    ])]),                 
                ])
            ]),
        ])