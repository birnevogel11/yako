from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from roly.test_case import TestCase, TestCaseGiven


class TestModuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    given: TestCaseGiven = TestCaseGiven()
    test_cases: list[TestCase] = []
