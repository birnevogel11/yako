import logging
from pathlib import Path
from typing import Annotated

import typer

from roly.runner.single_docker import run_single_test_docker_cli
from roly.runner.single_runner import run_single_test_cli
from roly.runner.test_runner import run_test_cli

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
        list[Path] | None, typer.Option("-c", "--config", help="config path")
    ] = None,
    verbose: Annotated[bool, typer.Option(help="Show debug log.")] = False,
) -> None:
    _init_logging(verbose)

    run_test_cli(base_path=base, config_path=config)


@app.command()
def single(
    path: Path,
    roles_path: Annotated[
        list[str] | None, typer.Option(help="Set extra role_path")
    ] = None,
    verbose: Annotated[bool, typer.Option(help="Show debug log.")] = False,
    capture_output: Annotated[
        bool, typer.Option(help="Capture output from ansible-playbook.")
    ] = True,
) -> None:
    _init_logging(verbose)

    run_single_test_cli(
        path, extra_roles_path=roles_path, capture_output=capture_output
    )


@app.command()
def single_docker(
    path: Path,
    roles_path: Annotated[
        list[str] | None, typer.Option(help="Set extra role_path")
    ] = None,
    verbose: Annotated[bool, typer.Option(help="Show debug log.")] = False,
    capture_output: Annotated[
        bool, typer.Option(help="Capture output from ansible-playbook.")
    ] = True,
) -> None:
    _init_logging(verbose)

    run_single_test_docker_cli(
        path, extra_roles_path=roles_path, capture_output=capture_output
    )


def main() -> None:
    app()
