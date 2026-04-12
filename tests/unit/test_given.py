from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pydantic
import pytest
from inline_snapshot import snapshot

from yako.given import CopyFileConfig, MockActionCustomConfig, TestCaseGiven

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("raw_file_field", "expected_file_field"),
    [
        (
            ["/path/to/src.txt"],
            snapshot([CopyFileConfig(src="/path/to/src.txt", dest="/path/to/src.txt")]),
        ),
        (
            [{"src": "/path/to/src.txt", "dest": "/path/to/dest.txt"}],
            snapshot(
                [CopyFileConfig(src="/path/to/src.txt", dest="/path/to/dest.txt")]
            ),
        ),
    ],
)
def test_parse_files_field(
    raw_file_field: list[Any], expected_file_field: list[CopyFileConfig]
) -> None:
    given = TestCaseGiven.model_validate({"files": raw_file_field})
    assert given.files == expected_file_field


def test_custom_action_config() -> None:
    raw_custom_action = {
        "custom_action": {
            "set_fact": {"answer": 42},
        }
    }

    custom_config = MockActionCustomConfig.model_validate(raw_custom_action)
    assert custom_config == snapshot(
        MockActionCustomConfig(custom_action={"set_fact": {"answer": 42}})
    )


def test_invalid_custom_action_config() -> None:
    raw_custom_action = {
        "custom_action": {
            "set_fact": {"answer": 42},
            "another_fact": {"answer": 43},
        }
    }

    with pytest.raises(pydantic.ValidationError) as err:
        MockActionCustomConfig.model_validate(raw_custom_action)

    assert json.loads(err.value.json()) == snapshot(
        [
            {
                "type": "value_error",
                "loc": ["custom_action"],
                "msg": "Value error, custom_action must have "
                "exactly one key-value pair",
                "input": {
                    "set_fact": {"answer": 42},
                    "another_fact": {"answer": 43},
                },
                "ctx": {"error": "custom_action must have exactly one key-value pair"},
                "url": "https://errors.pydantic.dev/2.12/v/value_error",
            }
        ]
    )
