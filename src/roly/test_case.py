from __future__ import annotations

import enum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from roly.consts import ROLY_TEST_CONFIG_KEY
from roly.given import TestCaseGiven
from roly.utils import not_test
from roly.yaml import safe_dump

if TYPE_CHECKING:
    import subprocess
    from typing import Self

    from roly.config import RolyConfig
    from roly.test_module import TestModuleInputConfig

logger = logging.getLogger(__name__)

PLAYBOOK_DEFAULT_CONTENT = {
    "hosts": "all",
    "any_errors_fatal": True,
    "gather_facts": False,
}


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

    name = f"{path}::{test_case_name}"
    if parametrize_name:
        name = f"{name}[{parametrize_name}]"

    return name


def _resolve_playbooks_path(
    test_module_path: Path, playbooks_path: list[str], base_dir: Path | None = None
) -> list[Path]:
    search_bases = [
        test_module_path.resolve().parent,
        (base_dir or Path.cwd()).resolve(),
    ]

    resolved_paths = []
    for name in playbooks_path:
        resolved_path = None
        if (resolved_path := Path(name)).is_absolute():
            logger.debug("%s is an absolute path. Skip to resolve it")
        else:
            resolved_path = next((base / name for base in search_bases), None)
            if not resolved_path:
                msg = (
                    f"Can not resolve the playbook path. "
                    f"test_module_path: {test_module_path}, "
                    f"playbook_path: {name}"
                )
                raise ValueError(msg)

        resolved_paths.append(resolved_path)

    return resolved_paths


def _validate_tasks_and_playbooks(test_case: TestCaseInputConfig | TestCase) -> None:
    if not test_case.playbooks and not test_case.tasks:
        msg = f"Test case require playbooks or tasks. name: {test_case.name}"
        raise ValueError(msg)

    if test_case.playbooks and test_case.tasks:
        msg = f"Test case can only provide playbooks or tasks. name: {test_case.name}"
        raise ValueError(msg)

    if not test_case.playbooks and not test_case.tasks:
        msg = f"Test case must contains playbooks or tasks. name: {test_case.name}"
        raise ValueError(msg)


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
        _validate_tasks_and_playbooks(self)

        return self


class TestCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path
    parametrized_name: str = ""
    display_name: str = ""
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[Path] = []
    tasks: list[dict[str, Any]] = []

    @classmethod
    def from_input_config(
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
                given=given,
                playbooks=_resolve_playbooks_path(
                    module_config.path, case_config.playbooks
                ),
                tasks=case_config.tasks,
            )
            for p_name, given in givens.items()
        ]

    def model_post_init(self, context: Any, /) -> None:
        object.__setattr__(
            self,
            "display_name",
            _create_test_case_display_name(
                self.path, self.name, self.parametrized_name
            ),
        )
        return super().model_post_init(context)

    @model_validator(mode="after")  # type: ignore[misc]
    def validate_content(self) -> Self:
        _validate_tasks_and_playbooks(self)

        return self

    def dump_roly_callback_config_file(self, output_path: Path) -> None:
        output_path.write_text(safe_dump({ROLY_TEST_CONFIG_KEY: self.model_dump()}))

    def is_match(self, filter_key: str) -> bool:
        return filter_key in self.display_name


class TestCaseResultState(enum.Enum):
    Success = "success"
    Failed = "failed"
    Error = "error"
    Skipped = "skipped"


class TestCaseResult(BaseModel):
    name: str = ""
    path: Path = Path.cwd()

    state: TestCaseResultState = TestCaseResultState.Success
    cmd: list[str] = []
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    test_case: TestCase | None = None

    @classmethod
    def from_test_case_and_cmd_result(
        cls, case: TestCase, cmd_result: subprocess.CompletedProcess[str]
    ) -> Self:
        return cls(
            name=case.display_name,
            path=case.path,
            state=(
                TestCaseResultState.Success
                if cmd_result.returncode == 0
                else TestCaseResultState.Failed
            ),
            cmd=cmd_result.args,
            return_code=cmd_result.returncode,
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            test_case=case,
        )

    @classmethod
    def from_skipped_test_case(cls, case: TestCase) -> Self:
        return cls(
            name=case.display_name,
            path=case.path,
            state=TestCaseResultState.Skipped,
            test_case=case,
        )


def make_content_playbook(raw_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**PLAYBOOK_DEFAULT_CONTENT, "tasks": raw_content}]
