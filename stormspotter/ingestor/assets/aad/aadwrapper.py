import json
from stormspotter.ingestor.utils import Recorder
from stormspotter.ingestor.assets.aad import AADObject, AADUser
from concurrent.futures import ThreadPoolExecutor, wait, as_completed


def query_aadobjects(context):
    aad_types = AADObject.__subclasses__()    
    tpe = ThreadPoolExecutor()
    futures = [tpe.submit(aad().query_resources, context) for aad in aad_types]
    for f in as_completed(futures):
        try:
            Recorder.writestr(f"{f.result()[0]}.json", json.dumps(f.result()[1:], sort_keys=True))
        except Exception as e:
            print(e)