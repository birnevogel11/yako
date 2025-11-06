from __future__ import annotations

import copy
import sys
from typing import TYPE_CHECKING, Self

from ansible import constants as C  # # noqa: N812
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar
from ansible.utils.display import Display
from pydantic import BaseModel

if TYPE_CHECKING:
    from typing import Any

    from ansible.executor.task_result import CallbackTaskResult
    from ansible.inventory.host import Host
    from ansible.playbook.play import Play
    from ansible.playbook.task import Task

global_display = Display()


ROLY_TEST_CONFIG_KEY = "ROLY_TEST_CASE_CONFIG"


def display_message_ok(msg: str, color=C.COLOR_OK) -> None:
    global_display.display(msg=f"[ROLY]: {msg}", color=color)


class RolyException(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        global_display.display(msg=f"[ROLY_ERROR]: {message}", color=C.COLOR_ERROR)
        sys.exit(exit_code)


class TaskTemplateExpander:
    def __init__(self, host: Host, task: Task, extra_vars: dict[str, Any] | None = None) -> None:
        self._extra_vars = extra_vars
        self._host = host
        self._task = task
        self._templar = Templar(
            loader=DataLoader(),
            variables=self._get_task_playbook_vars(self._host, self._task, self._extra_vars),
        )

    def _get_task_playbook_vars(self, host: Host, task: Task, extra_vars: dict[str, Any] | None = None) -> Any:
        # inventory + host vars + group vars
        playbook_vars = task.play.get_variable_manager().get_vars(host=host, task=task)
        # add play vars
        playbook_vars.update(task.play.vars)
        # add extra vars
        playbook_vars.update(self._extra_vars or {})

        return playbook_vars

    def expand(self, raw_str: str) -> str:
        return self._templar.template(raw_str)


class MockActionConfig(BaseModel):
    task_name: str
    role_name: str | None = None
    files: dict[str, str] = {}
    extra_vars: dict[str, str] = {}


class TestCaseGiven(BaseModel):
    files: dict[str, str] = {}
    extra_vars: dict[str, str] = {}
    mocks: list[MockActionConfig] = []


class TestCaseAssert(BaseModel):
    name: str = ""
    value: str = ""
    mode: str = "=="  # `==`(default), `!=`, `<`, `>`, `<=`, `>=`, `in`, `not_in`
    file: bool = False  # False (default), True


class TestConfig(BaseModel):
    name: str
    given: TestCaseGiven
    playbooks: list[str] = []
    assert_inputs: list[TestCaseAssert] = []
    assert_outputs: list[TestCaseAssert] = []

    @classmethod
    def from_playbook(cls, playbook_extra_vars: dict[str, Any]) -> Self:
        if not (raw_test_config := playbook_extra_vars.get(ROLY_TEST_CONFIG_KEY)):
            msg = f"{ROLY_TEST_CONFIG_KEY} not found!"
            raise RolyException(msg)

        # Variables placed into the config need to be instantiated with extra vars
        templar = Templar(loader=DataLoader(), variables=playbook_extra_vars)
        try:
            raw_test_config = templar.template(raw_test_config)
        except Exception as e:
            raise RolyException("Failed to expand config vars") from e

        return cls(**raw_test_config)


class RolyInternal(BaseModel):
    test_config: TestConfig

    def get_extra_vars(self) -> dict[str, Any]:
        return self.test_config.given.extra_vars


class CallbackModule(CallbackBase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._roly: RolyInternal = None  # type: ignore[assignment]

    def v2_playbook_on_play_start(self, play: Play) -> Play:

        playbook_extra_vars = play.get_variable_manager().extra_vars
        test_config = TestConfig.from_playbook(playbook_extra_vars)
        playbook_extra_vars.update(test_config.given.extra_vars)

        self._roly = RolyInternal(test_config=test_config)
        display_message_ok(f"Start Roly with test case - {self._roly.test_config.name}")

        return play

    def v2_runner_on_start(self, host: Host, task: Task) -> None:
        display_message_ok(f"Runner start: {task}, on host {host}, name: {task.name}")
        task_var_expander = TaskTemplateExpander(host, task, self._roly.get_extra_vars())

        new_task_name = task_var_expander.expand(task.name)
        new_task = copy.copy(task)
        new_task.task_name = new_task_name
        new_task._task_name = new_task_name  # noqa: SLF001
        new_task.ignore_errors = task_var_expander.expand(task.ignore_errors)

    def v2_runner_on_ok(self, result: CallbackTaskResult, *args, **kwargs) -> None:
        self._display.debug("Run v2_runner_on_ok")
