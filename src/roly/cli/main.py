from pathlib import Path

import typer

from roly.single_runner import run_single_test_cli

app = typer.Typer()


@app.command(name="list")
def list_tests() -> None:
    raise NotImplementedError


@app.command()
def single(path: Path) -> None:
    run_single_test_cli(path)


def main() -> None:
    app()
