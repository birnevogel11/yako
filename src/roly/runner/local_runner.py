from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from roly.ansible_config import make_roly_ansible_config

if TYPE_CHECKING:
    from typing import Any

    from roly.config import RolyConfig
    from roly.test_case import TestCase
    from roly.test_module import TestModule

logger = logging.getLogger(__name__)


PLAYBOOK_DEFAULT_CONTENT = {
    "hosts": "all",
    "any_errors_fatal": True,
}


def _make_content_playbook(raw_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**PLAYBOOK_DEFAULT_CONTENT, "tasks": raw_content}]


def _create_ansible_config(config: RolyConfig, base_dir: Path) -> Path:
    ansible_config_path = base_dir / "ansible.cfg"
    roles_path = [str(path) for path in config.ansible.expand_roles_path()]
    logger.debug("Create ansible config with roles path: %s", roles_path)
    make_roly_ansible_config(roles_path=roles_path, output_path=ansible_config_path)

    return ansible_config_path


def _list_test_cases(
    test_modules: list[TestModule], filter_key: str = ""
) -> list[TestCase]:
    test_cases = (
        test_case
        for test_module in test_modules
        for test_case in test_module.test_cases
    )
    if filter_key:
        test_cases = (
            test_case
            for test_case in test_cases
            if filter_key in test_case.display_name
        )

    return sorted(test_cases, key=lambda t: t.display_name)


class TestCaseResult(BaseModel):
    is_passed: bool = True
    test_case: TestCase


class RolyRuntimeContext(BaseModel):
    ansible_config_path: Path
    ansible_playbook_cmd: list[str]


def _run_test_case(
    config: RolyConfig, context: RolyRuntimeContext, case: TestCase
) -> TestCaseResult:
    raise NotImplementedError


def run_tests_local(
    config: RolyConfig, test_modules: list[TestModule], filter_key: str = ""
) -> None:
    with tempfile.TemporaryDirectory() as raw_base_dir:
        base_dir = Path(raw_base_dir)

        ansible_config_path = _create_ansible_config(config, base_dir)
        test_cases = _list_test_cases(test_modules, filter_key)
        # test_case_results = [_run_test_case(config, case) for case in test_cases]
