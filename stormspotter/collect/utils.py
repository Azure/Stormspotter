import sys
from itertools import islice
from pathlib import Path
from typing import Counter, Dict, List, Union

import aiosqlite
import msgpack
from rich import box
from rich.columns import Columns
from rich.console import RenderGroup
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table


def proactor_win32_patch(event):
    """Ignores Proactor loop errors on Windows"""
    if (
        event.exc_type == RuntimeError
        and str(event.exc_value) == "Event loop is closed"
    ):
        pass
    else:
        sys.__unraisablehook__(event)


def get_all_subclasses(cls):
    """Returns all subclasses of an object recursively"""
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in get_all_subclasses(c)]
    )


async def sqlite_writer(output: Path, res):
    """Writes results to sqlite file"""

    if not Path(output).exists():
        async with aiosqlite.connect(output) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS results 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                result blob)"""
            )
            await db.commit()

    async with aiosqlite.connect(output) as db:
        await db.execute_insert(
            "INSERT INTO results (result) VALUES (?)", (msgpack.dumps(res),)
        )
        await db.commit()


def chunk(data: Union[List, Dict], size: int):
    """Chunk a list or dict into even lists"""
    for idx in range(0, len(data), size):
        if isinstance(data, list):
            yield data[idx : idx + size]
        elif isinstance(data, dict):
            yield {key: data[key] for key in islice(data, size)}


def gen_results_tables(aad_results: Counter, arm_results: Counter) -> RenderGroup:
    """Generate live tables for results"""

    tables = []

    if aad_results:
        aad_table = Table(
            style="bold blue",
            title_style="bold cyan",
            box=box.HORIZONTALS,
            show_header=False,
            show_edge=False,
        )
        aad_table.add_column("Type", style="dodger_blue1")
        aad_table.add_column("Count", style="yellow")
        [aad_table.add_row(k, str(v)) for k, v in sorted(aad_results.items())]
        tables.append(
            Panel.fit(
                aad_table,
                title=f"[bold yellow]AAD Results (Total: {sum(aad_results.values())})[/]",
                border_style="bold blue",
                style="bold yellow",
            )
        )

    arm_results_group = []
    if arm_results:
        for chunked_list in chunk(
            sorted(arm_results.items()), len(arm_results) // 3 + 1
        ):
            arm_table = Table(
                style="bold blue",
                title_style="bold cyan",
                box=box.HORIZONTALS,
                show_edge=False,
                show_header=False,
                expand=True,
            )
            arm_table.add_column("Type", style="dodger_blue1")
            arm_table.add_column("Count", style="yellow")
            [arm_table.add_row(k, str(v)) for k, v in chunked_list]
            arm_results_group.append(arm_table)

        tables.append(
            Panel(
                Columns(
                    arm_results_group,
                    padding=(0, 1),
                    expand=True,
                    equal=True,
                ),
                title=f"[bold yellow]ARM Results (Total: {sum(arm_results.values())})[/]",
                border_style="bold blue",
            )
        )

    return Columns(
        tables,
        padding=(1, 1),
    )
