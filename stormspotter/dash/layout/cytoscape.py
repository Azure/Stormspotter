from itertools import cycle, islice
from stormspotter.dash.core.context import DashParser
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_core_components as dcc
import dash_cytoscape as dcy
from .labels import NODE_LABELS

klay = {'name':"klay",
            "nodeDimensionsIncludeLabels": True,
            "klay": {
                "compactComponents": True,
                "direction": "DOWN",
                "layoutHierarchy": False,
                "nodeLayering": "NETWORK_SIMPLEX",
                "thoroughness": 30,
                "nodePlacement": "SIMPLE"
            }
        }

cb = {"name": "cose-bilkent",
        "nodeDimensionsIncludeLabels": True,
        "animate": False,
        "idealEdgeLength": 75,
        "randomize": True,
        "nodeRepulsion": 5000,
        "numIter": 5000
        }

cola = {"name": "cola",
        "nodeDimensionsIncludeLabels": True,
        "animate": False,
        }

dagre = {"name": "dagre",
        "nodeDimensionsIncludeLabels": True,
        "animate": False,
        }

NODE_LAYOUTS = cycle([cb, dagre, klay])
 
cyto = dcy.Cytoscape(
    id="cy",
    layout=next(NODE_LAYOUTS),
    style={'width': '100%', 'height': '100%'},
    elements=[],
    stylesheet=[
    {
        'selector': 'node',
        'style': {
            'content': 'data(label)',
            'color': 'white',
            'font-size': 8,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'background-fit': 'contain',
            'background-clip': 'none',
            'text-background-color': '#00001a',
            'text-background-opacity': 0.7,
            'text-background-padding': 1,
            'text-background-shape': 'roundrectangle',
            'min-zoomed-font-size': 8,
            'background-color': '#003366',
            'background-opacity': 0,
            'overlay-color': "white",
            'font-family': "Cascadia Mono",
            'background-image': "url(../assets/images/generic.png)"
        }
    }, 
    {
        'selector': 'edge',
        'style': {
            'width': '2px',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': 'white',
            'target-arrow-fill': 'filled',
            'control-point-step-size': '140px',
            'label': 'data(label)',
            'color': 'white',
            'line-color': '#666362',
            'font-size': '8',
            'curve-style': 'bezier',
            'text-rotation': 'autorotate',
            'text-valign': 'top',
            'text-margin-y': -10,
            'text-background-color': '#00001a',
            'min-zoomed-font-size': 8,
            'font-family': "Cascadia Mono",
        }
    }] +
    [{
        'selector': f'node[type = "{nodetype}"]',
        'style': {
            'background-image': f"{url}",
        }
    } for nodetype, url in NODE_LABELS] +
    [{
        'selector': ':selected',
        "style": {
            "border-opacity": 1,
            "opacity": 1,
            "color": "#ff7f00",
            'z-index': 9999
        }
    },
        {
        'selector': '.followerNode',
        'style': {
            'background-color': '#0074D9'
        }
    },
    {
        'selector': '.followerEdge',
        "style": {
            "line-color": "#FC6A03",
            "z-index": 9999,
            "opacity": 1,

        }
    },
    {
        'selector': '.followingNode',
        'style': {
            "background-color": '#FF4136'
        }
    },
    {
        'selector': '.followingEdge',
        "style": {
            "line-color": "#A0FA82",
            "z-index": 9999,
            "opacity": 1,

        }
    },
    {
        'selector': f'node[!type]',
        'style': {
            'background-image': "url(../assets/images/none.png)",
        }
    }
    ]
)