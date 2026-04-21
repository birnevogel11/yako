from __future__ import annotations

import enum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from yako.consts import YAKO_TEST_CONFIG_KEY
from yako.given import TestCaseGiven
from yako.utils import not_test
from yako.yaml import safe_dump

if TYPE_CHECKING:
    import subprocess
    from typing import Self

    from yako.config import YakoConfig, RepoRoleConfig
    from yako.test_module import TestModuleInputConfig

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

def _resolve_roles_path(
    test_module_path: Path, roles_path: list[str], base_dirs: list[Path] = [],
ansible_roles_paths: list[Path] = []) -> list[Path]:
    search_bases = [
        test_module_path.resolve().parent,
        Path.cwd()
    ]

    search_bases.extend([p.resolve() for p in ansible_roles_paths])
    search_bases.extend([p.resolve() for p in base_dirs])

    resolved_paths = []
    for name in roles_path:
        resolved_path = None
        if (resolved_path := Path(name)).is_absolute():
            logger.debug("%s is an absolute path. Skip to resolve it")
        else:
            resolved_path = next((base / name for base in search_bases), None)
            if not resolved_path:
                msg = (
                    f"Can not resolve the role path. "
                    f"test_module_path: {test_module_path}, "
                    f"role_path: {name}"
                )
                raise ValueError(msg)

        resolved_paths.append(resolved_path)

    return resolved_paths

def _validate_tasks_and_playbooks(test_case: TestCaseInputConfig | TestCase) -> None:
    fields = [test_case.playbooks, test_case.roles, test_case.tasks]
    fields_exist = [f for f in fields if f]

    if len(fields_exist) == 0:
        msg = ("Test case requires playbooks, roles, or tasks. ",
               f"name: {test_case.name}")
        raise ValueError("".join(msg))

    if len(fields_exist) > 1:
        msg = ("Test case can only provide one of: ",
               f"playbooks, roles, or tasks. name: {test_case.name}")
        raise ValueError("".join(msg))


@not_test
class TestCaseInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
    roles: list[str] = []
    tasks: list[dict[str, Any]] = []
    parametrize: dict[str, TestCaseGiven] = {}

    @model_validator(mode="after")
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
    roles: list[Path] = []
    tasks: list[dict[str, Any]] = []

    @classmethod
    def from_input_config(
        cls,
        config: YakoConfig,
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

        roles_paths = [Path(p.path if isinstance(p, RepoRoleConfig) else p) for p in config.ansible.roles_path]
        return [
            cls(
                name=case_config.name,
                path=module_config.path,
                parametrized_name=p_name,
                given=given,
                playbooks=_resolve_playbooks_path(
                    module_config.path, case_config.playbooks
                ),
                roles=_resolve_roles_path(
                    module_config.path, case_config.roles,
                    config.base_dir, roles_paths
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

    def list_only_name(self) -> str:
        return (
            f"{self.name}[self.parametrized_name]"
            if self.parametrized_name
            else self.name
        )

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        _validate_tasks_and_playbooks(self)

        return self

    def dump_yako_callback_config(
        self, output_path: Path | None = None
    ) -> dict[str, Any]:
        callback_config = {YAKO_TEST_CONFIG_KEY: self.model_dump(by_alias=True)}
        if output_path:
            output_path.write_text(safe_dump(callback_config))
        return callback_config

    def is_match(self, filter_key: str) -> bool:
        return filter_key in self.display_name

    def has_playbooks(self) -> bool:
        return bool(self.playbooks)

    def has_roles(self) -> bool:
        return bool(self.roles)

    def does_playbook_exists(self) -> bool:
        return bool(self.playbooks) and all(p.exists() for p in self.playbooks)

    def not_found_playbooks(self) -> list[Path]:
        return [p for p in self.playbooks if not p.exists()]

    def does_role_exists(self) -> bool:
        return bool(self.roles) and all(p.exists() for p in self.roles)

    def not_found_roles(self) -> list[Path]:
        return [p for p in self.roles if not p.exists()]


class TestCaseResultState(enum.Enum):
    Success = "pass"
    Failed = "failed"
    Error = "error"
    Skipped = "skipped"

    def to_short_result_str(self) -> str:
        return TEST_CASE_RESULT_STATE_SHORT_MAPPING[self]

    def to_result_str(self) -> str:
        return self.value.upper()


TEST_CASE_RESULT_STATE_SHORT_MAPPING = {
    TestCaseResultState.Success: ".",
    TestCaseResultState.Failed: "F",
    TestCaseResultState.Error: "E",
    TestCaseResultState.Skipped: "S",
}


class TestCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = ""
    path: Path = Path.cwd()

    state: TestCaseResultState = TestCaseResultState.Success
    cmd: list[str] = []
    return_code: int = 0
    msg: str = ""
    stdout: str = ""
    stderr: str = ""
    test_case: TestCase | None = None
    execution_time_secs: float = 0.0

    @classmethod
    def from_test_case_and_cmd_result(
        cls,
        case: TestCase,
        cmd_result: subprocess.CompletedProcess[str],
        execution_time_secs: float = 0.0,
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
            execution_time_secs=execution_time_secs,
        )

    @classmethod
    def from_skipped_test_case(cls, case: TestCase) -> Self:
        return cls(
            name=case.display_name,
            path=case.path,
            state=TestCaseResultState.Skipped,
            test_case=case,
        )

    @classmethod
    def from_failed_without_playbooks_test_case(cls, case: TestCase) -> Self:
        return cls(
            name=case.display_name,
            path=case.path,
            state=TestCaseResultState.Error,
            test_case=case,
            msg=(
                "Test case has playbooks but they do not exist. "
                f"not found playbooks: {case.not_found_playbooks()}"
            ),
        )


def make_tasks_playbook(raw_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**PLAYBOOK_DEFAULT_CONTENT, "tasks": raw_content}]

def make_roles_playbook(raw_content: list[str]) -> list[dict[str, Any]]:
    return [{**PLAYBOOK_DEFAULT_CONTENT, "roles": raw_content}]
