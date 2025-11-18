from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from roly.given import TestCaseGiven


class TestCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
