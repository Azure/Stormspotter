import argparse
import asyncio
import shutil
import sys
import time

from loguru import logger

from stormcollector import OUTPUT_FOLDER
from stormcollector.aad import query_aad
from stormcollector.arm import query_arm
from stormcollector.auth import Context

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    import uvloop

    uvloop.install()


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
        "--subs",
        nargs="+",
        help="Subscriptions you wish to scan. Multiple subscriptions can be added as a space deliminated list --subs subid1 subid2",
    )

    parentParser.add_argument(
        "--nosubs",
        nargs="+",
        help="Subscriptions you wish to exclude from scanning. Multiple subscriptions can be added as a space deliminated list --nosubs subid1 subid2",
    )

    parser = argparse.ArgumentParser()
    authParser = parser.add_subparsers(help="Methods of authentication", dest="auth")

    cliParser = authParser.add_parser("cli", parents=[parentParser])
    cliParser.set_defaults(get_creds=Context.auth)

    # SPN AUTH #
    spnParser = authParser.add_parser("spn", parents=[parentParser])
    spnParser.add_argument(
        "--clientid", "-c", metavar="", required=True, help="Client ID"
    )
    spnParser.add_argument(
        "--secret", "-s", metavar="", required=True, help="Client Secret"
    )
    spnParser.add_argument(
        "--tenantid", "-t", metavar="", required=True, help="Tenant ID",
    )

    spnParser.set_defaults(get_creds=Context.auth)

    args = parser.parse_args()
    if hasattr(args, "get_creds"):
        start_time = time.time()

        asyncio.run(run(args))
        shutil.make_archive(OUTPUT_FOLDER, "zip", OUTPUT_FOLDER)
        logger.info(
            f"--- COMPLETE: {time.time() - start_time} seconds. OUTPUT FOLDER: {OUTPUT_FOLDER.absolute()}.zip ---"
        )
        shutil.rmtree(OUTPUT_FOLDER)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
