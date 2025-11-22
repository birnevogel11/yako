from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import pytest
from inline_snapshot import snapshot

from roly.plugins.module.roly_assert import run_module
from tests.unit.plugin.module.utils import run_ansible_module

if TYPE_CHECKING:
    from typing import Any


_run_roly_assert_module = functools.partial(run_ansible_module, run_module)


def test_roly_assert_help_function() -> None:
    assert _run_roly_assert_module(expected_failed=True)["failed"]


@pytest.mark.parametrize(
    ("actual_value", "expected_value"),
    [
        (42, 42),
        ({"a": 1}, {"a": 1}),
        ([], []),
        ([1, 2, 3], [1, 2, 3]),
        (3.14, 3.14),
    ],
)
def test_roly_assert_equal(actual_value: Any, expected_value: Any) -> None:
    assert "failed" not in _run_roly_assert_module(
        {"actual": actual_value, "expected": expected_value}
    )


@pytest.mark.parametrize(
    ("actual_value", "expected_value", "msg"),
    [
        (
            42,
            43,
            snapshot(
                """\
fail(s):

'42' != '43'
- 42
+ 43
""",
            ),
        ),
        (
            {"a": 1},
            {"a": 2},
            snapshot(
                """\
fail(s):

"{'a': 1}" != "{'a': 2}"
- {'a': 1}
?       ^
+ {'a': 2}
?       ^
""",
            ),
        ),
        (
            [1, 2, 3],
            [1, 2],
            snapshot(
                """\
fail(s):

'[1, 2, 3]' != '[1, 2]'
- [1, 2, 3]
?      ---
+ [1, 2]
""",
            ),
        ),
        (
            [1, 2, 3],
            [1, 2, 4],
            snapshot(
                """\
fail(s):

'[1, 2, 3]' != '[1, 2, 4]'
- [1, 2, 3]
?        ^
+ [1, 2, 4]
?        ^
""",
            ),
        ),
        (
            3.14,
            2.71,
            snapshot(
                """\
fail(s):

'3.14' != '2.71'
- 3.14
+ 2.71
""",
            ),
        ),
    ],
)
def test_roly_assert_failed(actual_value: Any, expected_value: Any, msg: str) -> None:
    result = _run_roly_assert_module(
        {"actual": actual_value, "expected": expected_value}, expected_failed=True
    )
    assert result["msg"] == msg
    assert result["failed"]


def test_roly_assert_equal_stmts() -> None:
    result = _run_roly_assert_module(
        {
            "stmts": [
                {"actual": 5, "expected": 5},
                {"actual": 5, "expected": 6, "mode": "!="},
            ],
        },
    )
    assert not result["changed"]


def test_roly_assert_equal_stmts_failed() -> None:
    result = _run_roly_assert_module(
        {
            "stmts": [
                {"actual": 5, "expected": 5},
                {"actual": 5, "expected": 6},
                {"actual": [], "expected": [1, 2, 3]},
                {"actual": {"a": 1, "b": 2}, "expected": {"b": 2}},
            ],
        },
        expected_failed=True,
    )

    assert result["msg"] == snapshot(
        """\
fail(s):

5 != 6

=======

Lists differ: [] != [1, 2, 3]

Second list contains 3 additional elements.
First extra element 0:
1

- []
+ [1, 2, 3]

=======

{'a': 1, 'b': 2} != {'b': 2}
- {'a': 1, 'b': 2}
+ {'b': 2}\
""",
    )
