import logging
from pathlib import Path
from typing import Annotated

import typer

from roly.single_runner import run_single_test_cli

app = typer.Typer()


def _init_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO if not verbose else logging.DEBUG,
        format="[%(asctime)s][%(levelname)-5.5s][%(name)s] %(message)s",
    )


@app.command(name="list")
def list_tests() -> None:
    raise NotImplementedError


@app.command()
def single(path: Path, verbose: Annotated[bool, typer.Option(help="Show debug log.")] = False) -> None:
    _init_logging(verbose)

    run_single_test_cli(path)


def main() -> None:
    app()
