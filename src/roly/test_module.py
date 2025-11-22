from __future__ import annotations

from pathlib import Path  # noqa: TC003

from pydantic import BaseModel, ConfigDict

from roly.test_case import TestCaseConfig, TestCaseGiven, TestCaseInputConfig


class TestModuleInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path | None = None
    given: TestCaseGiven = TestCaseGiven()
    test_cases: list[TestCaseInputConfig] = []


class TestModuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path | None = None
    test_cases: list[TestCaseConfig] = []
