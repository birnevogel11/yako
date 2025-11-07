from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING, Any, Self

from ansible import constants as C  # # noqa: N812
from ansible.errors import AnsibleUndefinedVariable
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar
from ansible.utils.display import Display
from pydantic import BaseModel

if TYPE_CHECKING:
    from ansible.executor.task_result import CallbackTaskResult
    from ansible.inventory.host import Host
    from ansible.playbook.play import Play
    from ansible.playbook.task import Task

global_display = Display()


ROLY_TEST_CONFIG_KEY = "ROLY_TEST_CASE_CONFIG"


def display_message_ok(msg: str, color=C.COLOR_OK) -> None:
    global_display.display(msg=f"[ROLY]: {msg}", color=color)


class RolyError(Exception):
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
    result_vars: dict[str, Any] = {}
    files: dict[str, str] = {}
    consider_changed: bool = False
    custom_action: str | None = None
    custom_action_args: dict[str, Any] = {}


class TestCaseAssert(BaseModel):
    name: str = ""
    value: str = ""
    mode: str = "=="  # `==`(default), `!=`, `<`, `>`, `<=`, `>=`, `in`, `not_in`
    file: bool = False  # False (default), True


class TestTaskConfig(BaseModel):
    name: str
    extra_vars: dict[str, Any] = {}
    mock: MockActionConfig | None = None
    assert_inputs: list[TestCaseAssert] = []
    assert_outputs: list[TestCaseAssert] = []

    # TODO(Birnevogel11): it's for double check. let's skip it now
    # role_name: str | None = None  # noqa: ERA001


class TestCaseGiven(BaseModel):
    files: dict[str, str] = {}
    extra_vars: dict[str, Any] = {}
    tasks: list[TestTaskConfig] = []


class RolyTestConfig(BaseModel):
    name: str
    given: TestCaseGiven
    playbooks: list[str] = []
    play_extra_vars: dict[str, Any] = {}

    @classmethod
    def from_playbook(cls, play_extra_vars: dict[str, Any]) -> Self:
        if not (raw_test_config := play_extra_vars.get(ROLY_TEST_CONFIG_KEY)):
            msg = f"{ROLY_TEST_CONFIG_KEY} not found!"
            raise RolyError(msg)

        # Variables placed into the config need to be instantiated with extra vars
        templar = Templar(loader=DataLoader(), variables=play_extra_vars)
        try:
            raw_test_config = templar.template(raw_test_config)
        except Exception as e:
            raise RolyError("Failed to expand config vars") from e

        raw_test_config["play_extra_vars"] = play_extra_vars

        return cls(**raw_test_config)


class VariableTemplar:
    def __init__(self, host: Host, task: Task, task_config: TestTaskConfig, config: RolyTestConfig) -> None:
        self._host = host
        self._task = task
        self._task_config = task_config
        self._test_extra_vars = config.given.extra_vars

        self._playbook_vars = self._get_task_playbook_vars(host, task)
        # inventory + host vars + group vars + play vars + test case extra vars
        self._playbook_task_templar = Templar(DataLoader(), self._playbook_vars)
        # inventory + host vars + group vars + play vars + test case extra vars + task extra vars
        self._playbook_task_extra_vars_templar = self._prepare_task_config_extra_vars(
            task_config,
            self._playbook_task_templar,
        )

    def _get_task_playbook_vars(self, host: Host, task: Task, extra_vars: dict[str, Any] | None = None) -> Any:
        # inventory + host vars + group vars
        playbook_vars = task.play.get_variable_manager().get_vars(host=host, task=task)
        # add play vars
        playbook_vars.update(task.play.vars)
        # add extra vars
        playbook_vars.update(self._test_extra_vars or {})

    def _prepare_task_config_extra_vars(self, task_config: TestTaskConfig, playbook_task_templar: Templar) -> Templar:
        task_extra_vars = task_config.extra_vars
        templated_task_extra_vars = playbook_task_templar.template(task_extra_vars)
        # then template the module args
        return Templar(loader=DataLoader(), variables=templated_task_extra_vars)

    def template_task(self, raw: Any) -> Any:
        return self._playbook_task_templar.template(raw)

    def template_task_with_extra_var(self, raw: Any) -> Any:
        return self._playbook_task_extra_vars_templar.template(raw)


class RolyInternalState(BaseModel):
    test_config: RolyTestConfig
    task_config: TestTaskConfig | None = None
    var_templar: VariableTemplar | None = None

    class Config:
        arbitrary_types_allowed = True

    def assign_current_task_config(self, host: Host, task: Task) -> None:
        task_config = self._find_task_config(host, task)
        self.task_config = task_config
        self.var_templar = (
            VariableTemplar(host, task, self.task_config, self.test_config) if self.task_config else None
        )

    def _find_task_config(self, host: Host, task: Task) -> TestTaskConfig | None:
        task_var_expander = TaskTemplateExpander(host, task, self.test_config.given.extra_vars)

        new_task_name = task_var_expander.expand(task.name)

        # TODO(bv11): Fix it - move ignore errors to another place
        # new_task = copy.copy(task)
        # new_task.task_name = new_task_name
        # new_task._task_name = new_task_name
        # new_task.ignore_errors = task_var_expander.expand(task.ignore_errors)

        return next(
            (task_config for task_config in self.test_config.given.tasks if new_task_name == task_config.name),
            None,
        )


def _mock_task(task: Task, task_config: TestTaskConfig) -> None:
    """
    Replace the task action with the roly_mock module and set its arguments.

    Caution: It changes the `task` argument in place.
    """
    if not task_config.mock:
        return

    new_action_name = task_config.mock.custom_action if task_config.mock.custom_action else "roly_mock"
    original_action_name = task.action
    display_message_ok(
        f"mock module - Before: '{original_action_name}' Now: '{new_action_name}' with custom action",
    )

    # Run a custom action
    if task_config.mock.custom_action:
        task.action = new_action_name
        task.resolved_action = new_action_name
        task.args = task_config.mock.custom_action_args
    else:
        # Run the default roly_mock action to return custom dicts and set changed status
        # TODO(Birnevogel11): support file copy
        new_action_name = "roly_mock"
        original_action_name = task.action

        display_message_ok(f"mock module - Before: '{original_action_name}' Now: '{new_action_name}'")

        task.action = new_action_name
        task.resolved_action = new_action_name
        task.args = {
            "task_name": task.name,
            "original_module_name": original_action_name,
            "consider_changed": task_config.mock.consider_changed,
            "result_dict": task_config.mock.result_vars,
        }


class CallbackModule(CallbackBase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._roly: RolyTestConfig = None  # type: ignore[assignment]
        self._roly_state: RolyInternalState = None  # type: ignore[assignment]

    def v2_playbook_on_play_start(self, play: Play) -> Play:
        play_extra_vars = play.get_variable_manager().extra_vars
        test_config = RolyTestConfig.from_playbook(play_extra_vars)
        play_extra_vars.update(test_config.given.extra_vars)
        print(play_extra_vars)

        self._roly = test_config
        self._roly_state = RolyInternalState(test_config=test_config)
        display_message_ok(f"Start Roly with test case - {self._roly.name}")

        return play

    def v2_runner_on_start(self, host: Host, task: Task) -> None:
        display_message_ok(f"Runner start: {task}, on host {host}, name: {task.name}")

        self._roly_state.assign_current_task_config(host, task)
        display_message_ok(f"{self._roly_state.task_config}")

        if (task_config := self._roly_state.task_config) and (var_templar := self._roly_state.var_templar):
            # Apply extra variables in task level
            with contextlib.suppress(AnsibleUndefinedVariable):
                task.args = var_templar.template_task_with_extra_var(task.args)

            # Check inputs
            if task_config.assert_inputs:
                raise NotImplementedError

            # Mock the task
            if task_config.mock:
                _mock_task(task, task_config)

        return super().v2_runner_on_start(host, task)

    def v2_runner_on_ok(self, result: CallbackTaskResult, *args, **kwargs) -> None:
        self._display.debug("Run v2_runner_on_ok")
