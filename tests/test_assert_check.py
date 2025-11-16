import pprint

from roly.assert_check import AssertMode, assert_value


def test_assert_check_true() -> None:
    result = assert_value({"a": 1}, {"a": 2}, mode=AssertMode.Equal)
    print(pprint.pformat(result.model_dump()))
