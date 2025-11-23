from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from roly.given import TestCaseGiven
from roly.utils import not_test

if TYPE_CHECKING:
    from typing import Self

    from roly.config import RolyConfig
    from roly.test_module import TestModuleInputConfig


def _create_test_case_display_name(
    model_path: Path,
    test_case_name: str,
    parametrize_name: str = "",
    base_dir: Path | None = None,
) -> str:
    base_dir = base_dir or Path.cwd()

    path = (
        model_path.relative_to(base_dir)
        if model_path.is_absolute() and model_path.is_relative_to(base_dir)
        else model_path
    )
    return (
        f"{path}::{test_case_name}[{parametrize_name}]"
        if parametrize_name
        else f"{path}::{test_case_name}"
    )


@not_test
class TestCaseInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
    tasks: list[dict[str, Any]] = []
    parametrize: dict[str, TestCaseGiven] = {}

    @model_validator(mode="after")  # type: ignore[misc]
    def validate_content(self) -> Self:
        if not self.playbooks and not self.tasks:
            msg = f"Test case require playbooks or tasks. name: {self.name}"
            raise ValueError(msg)

        if self.playbooks and self.tasks:
            msg = f"Test case can only provide playbooks or tasks. name: {self.name}"
            raise ValueError(msg)

        return self


class TestCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    parametrized_name: str = ""
    display_name: str = ""
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
    tasks: list[dict[str, Any]] = []

    @classmethod
    def from_config(
        cls,
        config: RolyConfig,
        module_config: TestModuleInputConfig,
        case_config: TestCaseInputConfig,
    ) -> list[Self]:
        if not case_config.parametrize:
            givens = {
                "": TestCaseGiven.from_merge(
                    config.given, module_config.given, case_config.given
                )
            }
        else:
            base_given = TestCaseGiven.from_merge(
                config.given, module_config.given, case_config.given
            )
            givens = {
                name: TestCaseGiven.from_merge(base_given, given)
                for name, given in case_config.parametrize.items()
            }

        return [
            cls(
                name=case_config.name,
                path=module_config.path,
                parametrized_name=p_name,
                display_name=_create_test_case_display_name(
                    module_config.path, case_config.name, p_name
                ),
                given=given,
                playbooks=case_config.playbooks,
                tasks=case_config.tasks,
            )
            for p_name, given in givens.items()
        ]
