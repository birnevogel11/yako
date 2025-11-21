from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import NewType

from pydantic import BaseModel, ConfigDict

from roly.test_case import TestCaseGiven

Repo = NewType("Repo", str)


class RunnerMode(Enum):
    Docker = "docker"
    Local = "Local"


class AnsiblePlaybookCommandConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    verbose: bool = True
    connection: str = "local"
    inventory: str = "127.0.0.1"
    limit: str = "127.0.0.1,"
    extra_args: list[str] = []


class RepoRoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo: Repo
    path: str = "roles"


class RepoPlaybookConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo: Repo
    path: str = "playbooks"


class AnsibleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    role_paths: list[Path | RepoRoleConfig] = []
    playbook_paths: list[Path | RepoPlaybookConfig] = []
    repo_staging: dict[Repo, Path] = {}
    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()


class LocalRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()


class DockerRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_name: str = ""  # TODO: fill roly by default
    # dockerfile: Path = ""  # TODO: Should we support it?  # noqa: ERA001
    workspace_dir: Path = Path("/tmp/workspace")  # noqa: S108
    extra_args: list[str] = []

    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()


class RunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    local: LocalRunnerConfig | None = None
    docker: DockerRunnerConfig | None = None


class RolyConfig(BaseModel):
    base_dir: Path = Path("test/roly")
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerConfig = RunnerConfig()
    given: TestCaseGiven = TestCaseGiven()
