import logging
from pathlib import Path
from typing import Annotated

import typer

from roly.runner.runner import run_tests_cli

app = typer.Typer()


def _init_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.INFO if not verbose else logging.DEBUG,
        format="[%(asctime)s][%(levelname)-5.5s][%(name)s] %(message)s",
    )


@app.command(name="list")
def list_tests() -> None:
    raise NotImplementedError


@app.command(name="test")
def run_tests(
    base: Annotated[list[Path] | None, typer.Argument(help="test path")] = None,
    config: Annotated[
        Path | None, typer.Option("-c", "--config", help="config path")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Show debug log.")
    ] = False,
    filter_key: Annotated[str | None, typer.Option(help="Filter tests by key")] = None,
) -> None:
    _init_logging(verbose)

    run_tests_cli(
        base_path=base, config_path=config, filter_key=filter_key or "", verbose=verbose
    )


def main() -> None:
    app()
