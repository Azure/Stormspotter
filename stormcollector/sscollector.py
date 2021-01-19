import argparse
import asyncio
import os
import shutil
import ssl
import sys
import time
from pathlib import Path

import aiohttp
from loguru import logger

from stormcollector import OUTPUT_FOLDER, SSL_CONTEXT
from stormcollector.aad import query_aad
from stormcollector.arm import query_arm
from stormcollector.auth import Context
from stormcollector.utils import json_convert, proactor_win32_patch

if sys.platform == "nix":
    import uvloop

    uvloop.install()
elif sys.platform == "win32":
    sys.unraisablehook = proactor_win32_patch


async def run(args: argparse.Namespace):
    context = await args.get_creds(args)

    tasks = []
    OUTPUT_FOLDER.mkdir(parents=True)
    if args.aad:
        tasks.append(query_aad(context, args))
    elif args.azure:
        tasks.append(query_arm(context, args))
    else:
        tasks.append(query_aad(context, args))
        tasks.append(query_arm(context, args))

    await asyncio.wait(tasks)
    await context.cred_async.close()

    if args.json:
        logger.info("Converting SQLite output to json")
        await json_convert(OUTPUT_FOLDER)
        logger.info("Finished SQLite to JSON conversion")


def main():
    parentParser = argparse.ArgumentParser(description="Stormcollector", add_help=False)

    configGroup = parentParser.add_mutually_exclusive_group()
    configGroup.add_argument(
        "--cloud",
        help="Built-in Cloud instance",
        default="PUBLIC",
        choices=["PUBLIC", "GERMAN", "CHINA", "USGOV"],
    )
    configGroup.add_argument(
        "--config", type=argparse.FileType("r"), help="Custom cloud instance"
    )

    resourceGroup = parentParser.add_mutually_exclusive_group()
    resourceGroup.add_argument(
        "--azure", help="Only scan Azure assets", action="store_true"
    )
    resourceGroup.add_argument(
        "--aad", help="Only scan AAD assets", action="store_true"
    )

    parentParser.add_argument(
        "--backfill",
        help="Perform AAD enumeration only for object IDs associated with RBAC enumeration. Only applicable when --azure is specified.",
        action="store_true",
    )
    parentParser.add_argument(
        "--subs",
        nargs="+",
        help="Subscriptions you wish to scan. Multiple subscriptions can be added as a space deliminated list --subs subid1 subid2",
    )

    parentParser.add_argument(
        "--nosubs",
        nargs="+",
        help="Subscriptions you wish to exclude from scanning. Multiple subscriptions can be excluded as a space deliminated list --nosubs subid1 subid2",
    )

    parentParser.add_argument(
        "--json", help="Convert sqlite output to json", action="store_true"
    )

    parentParser.add_argument(
        "--ssl-cert",
        help="SSL Cert to use for HTTP requests",
        type=argparse.FileType("r"),
    )

    parser = argparse.ArgumentParser()
    authParser = parser.add_subparsers(help="Methods of authentication", dest="auth")

    cliParser = authParser.add_parser("cli", parents=[parentParser])
    cliParser.set_defaults(get_creds=Context.auth)

    # SPN AUTH #
    spnParser = authParser.add_parser("spn", parents=[parentParser])
    spnParser.add_argument("--clientid", "-c", required=True, help="Client ID")
    spnParser.add_argument("--secret", "-s", required=True, help="Client Secret")
    spnParser.add_argument(
        "--tenantid", "-t", required=True, help="Tenant ID",
    )
    spnParser.set_defaults(get_creds=Context.auth)

    args = parser.parse_args()
    if hasattr(args, "get_creds"):
        start_time = time.time()

        if args.ssl_cert:
            cert_path = Path(args.ssl_cert.name).absolute()
            os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
            print(os.environ)
            sslcontext = ssl.create_default_context(cafile=cert_path)
            SSL_CONTEXT = aiohttp.TCPConnector(ssl_context=sslcontext)

        asyncio.run(run(args))
        logger.info(f"--- COMPLETE: {time.time() - start_time} seconds. ---")
        if any(Path(OUTPUT_FOLDER).iterdir()):
            logger.info("Zipping up output...")
            shutil.make_archive(OUTPUT_FOLDER, "zip", OUTPUT_FOLDER)
            logger.info(f"OUTPUT: {OUTPUT_FOLDER.absolute()}.zip")
        else:
            logger.warning("No output to create zip file!")

        shutil.rmtree(OUTPUT_FOLDER)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
