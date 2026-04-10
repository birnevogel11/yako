from __future__ import annotations

import functools

import pytest
from inline_snapshot import snapshot

from tests.unit.plugin.module.utils import run_ansible_module
from yako.plugins.module.yako_mock import run_module

_run_yako_mock_module = functools.partial(run_ansible_module, run_module)


def test_run_yako_mock_module() -> None:
    result = _run_yako_mock_module(expected_failed=True)
    assert result["failed"]
    assert result["msg"] == snapshot(
        "missing required arguments: original_module_name, task_name"
    )


@pytest.mark.parametrize("consider_changed", [True, False])
def test_run_yako_mock_module_basic(consider_changed: bool) -> None:
    result = _run_yako_mock_module(
        {
            "original_module_name": "banana",
            "task_name": "monkey",
            "consider_changed": consider_changed,
        },
    )
    assert result["changed"] == consider_changed
    assert result["msg"] == snapshot(
        "Yako Mock module called. Task name: monkey, Original module: banana"
    )


def test_run_yako_mock_module_with_return_value() -> None:
    result = _run_yako_mock_module(
        {
            "original_module_name": "banana",
            "task_name": "monkey",
            "result_dict": {"answer": 42},
        },
    )

    assert result["answer"] == 42
