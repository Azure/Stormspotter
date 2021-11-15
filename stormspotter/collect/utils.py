import sys
from pathlib import Path
from typing import Counter

import aiosqlite
import msgpack
from rich.console import RenderGroup
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


def gen_results_tables(aad_results: Counter, arm_results: Counter) -> RenderGroup:
    """Generate live tables for results"""

    tables = []

    if aad_results:
        aad_table = Table(
            title="AAD Results", style="bold green", title_style="bold cyan"
        )
        aad_table.add_column("Type", style="blue")
        aad_table.add_column("Count", style="cyan")
        [aad_table.add_row(k, str(v)) for k, v in sorted(aad_results.items())]

        tables.append(aad_table)

    if arm_results:
        arm_table = Table(
            title="ARM Results", style="bold green", title_style="bold cyan"
        )
        arm_table.add_column("Type", style="blue")
        arm_table.add_column("Count", style="cyan")
        [arm_table.add_row(k, str(v)) for k, v in sorted(arm_results.items())]

        tables.append(arm_table)

    return RenderGroup(*tables)
