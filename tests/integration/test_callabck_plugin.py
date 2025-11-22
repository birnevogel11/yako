from pathlib import Path

import pytest
import yaml
from roly.single_runner import run_single_test

TEST_PLAYBOOK_BASE_DIR = (Path(__file__).parent / "test_callback_plugin").resolve()


def _run_test(
    test_case_file_name: str, search_str: str, is_passed: bool = True
) -> None:
    result = run_single_test(TEST_PLAYBOOK_BASE_DIR / test_case_file_name)

    msgs = []
    if is_passed and result.returncode:
        msgs.append(f"Return code is {result.returncode}. Expected: 0")
    if search_str not in result.stdout:
        msgs.append(f"Can not found the string in stdout. str: '{search_str}'")

    if msgs:
        msg = "\n".join(
            (
                f"Test file failed: {test_case_file_name}",
                *msgs,
                result.stdout,
                result.stderr,
            )
        )
        raise AssertionError(msg)


def _list_test_cases(
    base_dir: Path,
    config_key: str = "ROLY_INTERNAL_INTEGRATION_TEST_CONFIG",
) -> list[tuple[str, str, bool]]:
    test_paths = [
        path
        for path in base_dir.iterdir()
        if path.is_file()
        and path.name.startswith("test")
        and path.name.endswith(".yaml")
    ]

    test_cases = []
    for path in test_paths:
        with path.open() as fin:
            raw_config = yaml.safe_load(fin)
            if test_config := raw_config.get(config_key, None):
                test_cases.append(
                    (
                        path.name,
                        test_config["search_keyword"],
                        test_config.get("is_passed", True),
                    )
                )

    return sorted(test_cases, key=lambda k: k[0])


@pytest.mark.integration
@pytest.mark.parametrize(
    ("test_case_file_name", "search_str", "is_pass"),
    _list_test_cases(TEST_PLAYBOOK_BASE_DIR),
)
def test_roly_callback(
    test_case_file_name: str, search_str: str, is_pass: bool
) -> None:
    _run_test(test_case_file_name, search_str, is_pass)
