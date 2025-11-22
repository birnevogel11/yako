from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from roly.given import TestCaseGiven

if TYPE_CHECKING:
    from typing import Self


class TestCaseInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path | None = None
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
    tasks: list[dict[str, Any]] = []

    @model_validator(mode="after")  # type: ignore[misc]
    def validate_content(self) -> Self:
        if not self.playbooks and not self.tasks:
            msg = f"Test case require playbooks or tasks. name: {self.name}"
            raise ValueError(msg)

        if self.playbooks and self.tasks:
            msg = f"Test case can only provide playbooks or tasks. name: {self.name}"
            raise ValueError(msg)

        return self


class TestCaseConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: Path | None = None
    given: TestCaseGiven = TestCaseGiven()
    playbooks: list[str] = []
