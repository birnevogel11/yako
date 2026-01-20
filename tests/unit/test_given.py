from __future__ import annotations

import pytest
from inline_snapshot import snapshot

from roly.given import CopyFileConfig, TestCaseGiven


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
def test_parse_files_field(raw_file_field, expected_file_field):
    given = TestCaseGiven.model_validate({"files": raw_file_field})
    assert given.files == expected_file_field
