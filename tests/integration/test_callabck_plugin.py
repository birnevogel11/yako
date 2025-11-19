from pathlib import Path

import pytest

from roly.single_runner import run_single_test

TEST_PLAYBOOK_BASE_DIR = (Path(__file__).parent / "test_callback_plugin").resolve()


def _run_test(test_case_file_name: str, search_str: str, is_pass: bool = True) -> None:
    result = run_single_test(TEST_PLAYBOOK_BASE_DIR / test_case_file_name)

    msgs = []
    if is_pass and result.returncode:
        msgs.append(f"Return code is {result.returncode}")
    if search_str not in result.stdout:
        msgs.append("Can not found the string in stdout. str: 'search_str'")

    if msgs:
        msg = "\n".join([f"Test file failed: {test_case_file_name}", *msgs, result.stdout])
        raise AssertionError(msg)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("test_case_file_name", "search_str", "is_pass"),
    [
        ("test_hello.yaml", "Hello World!", True),
        ("test_task_extra_vars.yaml", "A book: whats_life_mean_to_you", True),
        (
            "test_assert_input_fail.yaml",
            "[ROLY_ERROR]: Failed to assert inputs. task: Hello world, failed_asserts: 'Hello' != 'World' - name: msg",
            False,
        ),
    ],
)
def test_roly_callback_basic(test_case_file_name: str, search_str: str, is_pass: bool) -> None:
    _run_test(test_case_file_name, search_str, is_pass)
