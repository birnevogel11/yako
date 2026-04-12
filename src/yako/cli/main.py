import logging
from pathlib import Path
from typing import Annotated

import typer

from yako.plugin_cli import run_plugin_callback_test
from yako.repo import update_repo_cache
from yako.runner.runner import run_tests_cli

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
    filter_key: Annotated[
        str | None, typer.Option("-k", "--key", help="Filter tests by key")
    ] = None,
) -> None:
    _init_logging(verbose)

    run_tests_cli(
        base_path=base, config_path=config, filter_key=filter_key or "", verbose=verbose
    )


@app.command(name="test-callback")
def run_test_callback(
    path: Annotated[Path, typer.Argument(help="Native test path")],
) -> None:
    _init_logging(True)

    result = run_plugin_callback_test(path, capture_output=False)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


@app.command(name="update-cache")
def update_repo_cache_cli(
    config: Annotated[
        Path | None, typer.Option("-c", "--config", help="config path")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Show debug log.")
    ] = False,
) -> None:
    _init_logging(verbose)

    update_repo_cache(config)


def main() -> None:
    app()
