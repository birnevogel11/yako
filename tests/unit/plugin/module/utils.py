from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from ansible.module_utils.testing import patch_module_args

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


class MockSysExitError(Exception):
    pass


def _mock_sys_exit(code: int) -> None:
    if code != 0:
        msg = f"sys.exit called with code {code}"
        raise MockSysExitError(msg)


def run_ansible_module(
    run_module: Callable[[], None],
    module_args: dict[str, Any] | None = None,
    expected_failed: bool = False,
) -> dict[str, Any]:
    """Help to run the roly_assert module with optional module args."""
    module_args = module_args or {}

    context = (
        pytest.raises(MockSysExitError) if expected_failed else contextlib.nullcontext()
    )
    with (
        context,
        patch_module_args(module_args),
        patch("sys.exit", side_effect=_mock_sys_exit),
        patch(
            "ansible.module_utils.basic.AnsibleModule._record_module_result"
        ) as return_mock,
    ):
        run_module()

    return_mock.assert_called_once()

    return return_mock.call_args[0][0]
