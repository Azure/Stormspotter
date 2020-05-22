#!/usr/bin/env python3

import argparse
import getpass
import time
import json
from itertools import chain
from concurrent.futures import ThreadPoolExecutor, wait, as_completed
from stormspotter.collector.utils import Recorder, SSC as context
from stormspotter.collector.utils import Authentication, CloudContext
from stormspotter.collector.assets.aad import aadwrapper
from stormspotter.collector.assets.azure import azurewrapper

def main():
    parser = argparse.ArgumentParser(description='Stormspotter')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument("--service-principal", help='Use a service principal to authenticate', action="store_true")
    parser.add_argument("--tenant", help='Tenant Id for Service Principal Auth')
    parser.add_argument("--password", "-p", help='Credentials like user password, or for a service principal. Will prompt if not given.')
    parser.add_argument("--username", "-u", help='User name, service principal,')
    parser.add_argument("--cli", help='Use a service principal to authenticate', action="store_true")
    parser.add_argument("--azure-only", help='Only scan Azure assets', action="store_true")
    parser.add_argument("--aad-only", help='Only scan AAD assets', action="store_true")
    parser.add_argument("--subscription", "-s", nargs="+", help='Subscription you wish to scan. Multiple subscriptions can be added as a space deliminated list -s subid1 subid2')
    group.add_argument("--cloud", help="Built-in Cloud instance", default="PUBLIC")
    group.add_argument("--config-file", "-c", help="Custom cloud instance")

    args = parser.parse_args()
    context.cloudContext = CloudContext(args.cloud, args.config_file)

    try:
        context.auth = Authentication(
            args.cli,
            args.service_principal,
            args.username,
            args.password,
            args.tenant)
    except Exception as e:
        print(e)
        exit()

    start = time.time()

    if args.aad_only:
        aadwrapper.query_aadobjects(context)
    elif args.azure_only:
        azurewrapper.query_azure_subscriptions(context, args.subscription)
        azurewrapper.finalize(context)
    else:
        with ThreadPoolExecutor() as tpe:
            futures = list(chain([tpe.submit(aadwrapper.query_aadobjects, context)],
                         [tpe.submit(azurewrapper.query_azure_subscriptions, context, args.subscription)]
                         ))

            for f in as_completed(futures):
                try:
                    print(f.result())
                except:
                    print(f"ERROR: {f.exception()}")

    end = time.time()
    print(f"Completion Time: {end-start}")

if __name__ == '__main__':
    main()
