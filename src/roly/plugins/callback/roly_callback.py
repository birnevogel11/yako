from __future__ import annotations

import contextlib
import functools
import sys
from collections import ChainMap
from typing import TYPE_CHECKING, Any, ClassVar

from ansible import constants as C  # # noqa: N812
from ansible.errors import AnsibleUndefinedVariable
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar
from ansible.utils.display import Display
from pydantic import BaseModel, ConfigDict, ValidationError

from roly.given import TestTaskConfig  # noqa: TC001
from roly.test_case import TestCaseInputConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Literal, Self

    from ansible.executor.task_result import CallbackTaskResult
    from ansible.inventory.host import Host
    from ansible.playbook.play import Play
    from ansible.playbook.task import Task

    from roly.assert_check import AssertResult
    from roly.given import TestCaseAssert

global_display = Display()


def _display_message_ok(msg: str, color=C.COLOR_OK) -> None:
    global_display.display(msg=f"[ROLY]: {msg}", color=color)


def _get_task_playbook_vars(host: Host, task: Task, extra_vars: dict[str, Any] | None = None) -> Any:
    variables = {}
    variables.update(task.play.get_variable_manager().get_vars(host=host, task=task))
    variables.update(task.play.vars)
    variables.update(extra_vars or {})

    return variables


class RolyAnsiblePluginError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        if exit_code:
            global_display.display(msg=f"[ROLY_ERROR]: {message}", color=C.COLOR_ERROR)
        else:
            global_display.display(msg=f"[ROLY]: {message}", color=C.COLOR_OK)
        sys.exit(exit_code)


class RolyTestConfig(TestCaseInputConfig):
    model_config = ConfigDict(frozen=True)

    ROLY_TEST_CONFIG_KEY: ClassVar[str] = "ROLY_TEST_CASE_CONFIG"

    # The variable is from ansible, not found input config
    play_extra_vars_base: dict[str, Any] = {}  # noqa: RUF012

    @classmethod
    def from_playbook(cls, play_extra_vars_base: dict[str, Any]) -> Self:
        if not (raw_test_config := play_extra_vars_base.get(cls.ROLY_TEST_CONFIG_KEY)):
            msg = f"{cls.ROLY_TEST_CONFIG_KEY} not found!"
            raise RolyAnsiblePluginError(msg)

        # Variables placed into the config need to be instantiated with extra vars
        templar = Templar(loader=DataLoader(), variables=play_extra_vars_base)
        try:
            render_raw_test_config = {key: value for key, value in raw_test_config.items() if key != "tasks"}
            render_raw_test_config = templar.template(render_raw_test_config)
            raw_test_config.update(render_raw_test_config)
        except Exception as err:  # noqa: BLE001
            msg = f"Failed to expand config vars. err: {err}"
            raise RolyAnsiblePluginError(msg)  # noqa: B904

        raw_test_config["play_extra_vars_base"] = play_extra_vars_base

        return cls.model_validate(raw_test_config)


class SimpleVariableTemplar:
    def __init__(self, variables: Iterable[dict[str, Any]]) -> None:
        self._variables = dict(ChainMap(*variables))
        self._templar: Templar | None = None

    def template_task(self, raw: Any) -> Any:
        if not self._templar:
            self._templar = Templar(loader=DataLoader(), variables=self._variables)

        return self._templar.template(raw)


class VariableTemplar:
    def __init__(self, host: Host, task: Task, task_config: TestTaskConfig, config: RolyTestConfig) -> None:
        self._host = host
        self._task = task
        self._task_config = task_config

        self._playbook_vars = _get_task_playbook_vars(host, task)
        # inventory + host vars + group vars + play vars + test case extra vars
        self._playbook_task_templar = SimpleVariableTemplar((self._playbook_vars,))

    def template_task(self, raw: Any) -> Any:
        return self._playbook_task_templar.template_task(raw)

    def generate_task_loop_templar(self, loop_vars: dict[str, Any]) -> SimpleVariableTemplar:
        return SimpleVariableTemplar((self._playbook_vars, loop_vars))

    def generate_task_with_extra_var_templar(self) -> SimpleVariableTemplar:
        return SimpleVariableTemplar((self._playbook_vars, self.template_task(self._task_config.extra_vars)))


class RolyInternalState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    test_config: RolyTestConfig
    task_config: TestTaskConfig | None = None
    var_templar: VariableTemplar | None = None

    def assign_current_task_config(self, host: Host, task: Task) -> None:
        """Find and assign the roly task config and templar.

        Caution: It changes the `task` argument in place.
        """
        self.task_config, new_task_name, new_task_ignore_errors = self._find_task_config(host, task)
        self.var_templar = (
            VariableTemplar(host, task, self.task_config, self.test_config) if self.task_config else None
        )

        # Change task name and ignore error state
        task.task_name = new_task_name
        task._task_name = new_task_name  # noqa: SLF001
        task.ignore_errors = new_task_ignore_errors

    def _find_task_config(self, host: Host, task: Task) -> tuple[TestTaskConfig | None, str, bool]:
        task_var_expander = Templar(
            loader=DataLoader(),
            variables=_get_task_playbook_vars(host, task, self.test_config.given.extra_vars),
        )

        new_task_name = task_var_expander.template(task.name)
        return (
            next(
                (
                    task_config
                    for task_config in self.test_config.given.mock_tasks
                    if new_task_name == task_config.name
                ),
                None,
            ),
            new_task_name,
            task_var_expander.template(task.ignore_errors),
        )


def _mock_task(task: Task, task_config: TestTaskConfig) -> None:
    """Replace the task action with the roly_mock module and set its arguments.

    Caution: It changes the `task` argument in place.
    """
    if not task_config.mock:
        return

    original_action_name = task.action
    new_action_name, new_action_name_args = task_config.mock.gen_action(original_action_name)
    _display_message_ok(
        f"mock module - Before: '{original_action_name}' Now: '{new_action_name}' with custom action",
    )

    task.action = new_action_name
    task.resolved_action = new_action_name
    task.args = new_action_name_args


def _assert_stmts(
    stmts: list[TestCaseAssert],
    get_actual_value_func: Callable[[str], Any],
) -> tuple[list[AssertResult], list[AssertResult]]:
    test_results = [stmt.check(get_actual_value_func) for stmt in stmts]
    return [result for result in test_results if result.passed], [
        result for result in test_results if not result.passed
    ]


def _get_task_args(task_args: dict[str, Any], name: str) -> Any:
    return task_args[name]


def _assert_inputs_loop(task: Task, roly_state: RolyInternalState) -> None:
    if not (task_config := roly_state.task_config) or not (var_templar := roly_state.var_templar):
        return

    for loop_value in task.loop:
        loop_var_templar = var_templar.generate_task_loop_templar(loop_value)
        task_args = loop_var_templar.template_task(task.args)

        # Find one of match
        passed_asserts, failed_asserts = _assert_stmts(
            task_config.assert_inputs,
            functools.partial(_get_task_args, task_args),
        )
        if passed_asserts and not failed_asserts:
            return

    _report_assert(task.name, passed_asserts, failed_asserts, "inputs_loop")


def _assert_inputs_normal(task: Task, roly_state: RolyInternalState) -> None:
    if not (task_config := roly_state.task_config) or not (var_templar := roly_state.var_templar):
        return

    task_args = var_templar.template_task(task.args)
    passed_asserts, failed_asserts = _assert_stmts(
        task_config.assert_inputs,
        functools.partial(_get_task_args, task_args),
    )
    _report_assert(task.name, passed_asserts, failed_asserts, "inputs")


def _assert_inputs(task: Task, roly_state: RolyInternalState) -> None:
    if task.loop:
        _assert_inputs_loop(task, roly_state)
    else:
        _assert_inputs_normal(task, roly_state)


def _assert_outputs(task_config: TestTaskConfig, result_dict: dict[str, Any]) -> None:
    var_templar = Templar(loader=DataLoader(), variables=result_dict)
    passed_asserts, failed_asserts = _assert_stmts(
        task_config.assert_outputs,
        var_templar.resolve_variable_expression,
    )
    _report_assert(task_config.name, passed_asserts, failed_asserts, "outputs")


def _report_assert(
    task_name: str,
    passed_asserts: list[AssertResult],
    failed_asserts: list[AssertResult],
    state: Literal["inputs", "outputs", "inputs_loop"],
) -> None:
    if passed_asserts and not failed_asserts:
        _display_message_ok(f"Pass for assert {state}. task: {task_name}")
    if failed_asserts:
        failed_msgs = "\n".join(msg or "" for result in failed_asserts if (msg := result.err_msg or ""))
        msg = f"Failed to assert {state}. task: {task_name}, failed_asserts: {failed_msgs}"
        raise RolyAnsiblePluginError(msg)


def _assert_task_state(
    task_config: TestTaskConfig,
    should_be_changed: bool | None = None,
    should_be_skipped: bool | None = None,
    should_fail: bool | None = None,
    rescue_fail: bool = False,
) -> None:
    check_states = {
        "should_be_skipped": should_be_skipped,
        "should_be_changed": should_be_changed,
        "should_fail": should_fail,
    }

    err_msgs = []
    for var_name, actual_state in check_states.items():
        expected_state = getattr(task_config, var_name, None)
        if expected_state is not None and actual_state is not None:
            if expected_state != actual_state:
                err_msgs.append(f"Task {var_name} state error. actual: {actual_state}, expected: {expected_state}")
            else:
                _display_message_ok(f"{var_name} state check ok. expected_state: {expected_state}")

    if task_config.should_fail and task_config.should_fail == should_fail and rescue_fail:
        raise RolyAnsiblePluginError("Task failed as expected. Stop here with exit code 0", exit_code=0)

    if err_msgs:
        msg = "Check task state error: " + "\n".join(err_msgs)
        raise RolyAnsiblePluginError(msg)


class CallbackModule(CallbackBase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._roly: RolyInternalState = None  # type: ignore[assignment]

    def v2_playbook_on_play_start(self, play: Play) -> Play:
        play_extra_vars = play.get_variable_manager().extra_vars
        try:
            test_config = RolyTestConfig.from_playbook(play_extra_vars)
        except ValidationError as err:
            raise RolyAnsiblePluginError("Invalid Roly test case config") from err
        play_extra_vars.update(test_config.given.extra_vars)

        self._roly = RolyInternalState(test_config=test_config)
        _display_message_ok(f"Start Roly with test case - {self._roly.test_config.name}")

        return play

    def v2_runner_on_start(self, host: Host, task: Task) -> None:
        _display_message_ok(f"Runner start: {task}, on host {host}, name: {task.name}")

        self._roly.assign_current_task_config(host, task)
        _display_message_ok(f"{self._roly.task_config}")

        if (task_config := self._roly.task_config) and (var_templar := self._roly.var_templar):
            # Apply extra variables in task level. The mechanism does not apply to the case
            #   - name: "Example task"
            #     set_fact:
            #       another: "{{ task_extra_vars }}"  # noqa: ERA001
            with contextlib.suppress(AnsibleUndefinedVariable):
                task.args = var_templar.generate_task_with_extra_var_templar().template_task(task.args)
                print(task.args)

            # Check inputs
            if task_config.assert_inputs:
                _assert_inputs(task, self._roly)

            # Mock the task
            if task_config.mock:
                _mock_task(task, task_config)

        return super().v2_runner_on_start(host, task)

    def v2_runner_on_ok(self, result: CallbackTaskResult, *args, **kwargs) -> None:
        self._display.debug("Run v2_runner_on_ok")

        if task_config := self._roly.task_config:
            _assert_task_state(
                task_config,
                should_be_changed=result.is_changed(),
                should_be_skipped=False,
                should_fail=False,
            )

            if task_config.assert_outputs:
                _assert_outputs(task_config, result._result)  # noqa: SLF001

    def v2_runner_on_failed(self, result: CallbackTaskResult, *args, **kwargs) -> None:
        self._display.debug("Run v2_runner_on_failed")

        if task_config := self._roly.task_config:
            _assert_task_state(task_config, should_be_skipped=False, should_fail=True, rescue_fail=True)

    def v2_runner_on_skipped(self, result: CallbackTaskResult, **kwargs) -> None:
        self._display.debug("Run v2_runner_on_skipped")

        if task_config := self._roly.task_config:
            _assert_task_state(task_config, should_be_skipped=True, should_fail=False)
