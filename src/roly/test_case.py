from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from roly.given import TestCaseGiven

if TYPE_CHECKING:
    from typing import Self


class TestCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
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
