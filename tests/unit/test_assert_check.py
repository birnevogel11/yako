from inline_snapshot import snapshot

from roly.assert_check import AssertStmt


def test_assert_check_true() -> None:
    result = AssertStmt(actual={"a": 1}, expected={"b": 2}).check()
    assert not result.passed
    assert result.err_msg == snapshot(
        """\
{'a': 1} != {'b': 2}
- {'a': 1}
?   ^   ^

+ {'b': 2}
?   ^   ^
""",
    )
