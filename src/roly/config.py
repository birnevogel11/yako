from __future__ import annotations

import itertools
import logging
import os
from collections import ChainMap
from enum import Enum
from pathlib import Path
from typing import Self

import yaml
from pydantic import AnyUrl, BaseModel, ConfigDict
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from roly.consts import ROLY_CONFIG_PATH_ENV_NAME
from roly.test_case import TestCaseGiven

logger = logging.getLogger(__name__)


type Repo = AnyUrl


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

    @classmethod
    def from_merge(cls, *configs: Self) -> Self:
        if not configs:
            raise ValueError("Require at least one config")

        default_key_value = {
            "verbose": True,
            "connection": "local",
            "inventory": "127.0.0.1",
            "limit": "127.0.0.1,",
        }

        merge_config = configs[0].model_copy()
        for config in configs[1:]:
            merge_config = merge_config.model_copy(
                update={
                    key: value
                    for key, value in config.model_dump().items()
                    if key != "extra_args" and value != default_key_value[key]
                },
            )

        return merge_config.model_copy(
            update={
                "extra_args": list(
                    itertools.chain.from_iterable(
                        config.extra_args for config in configs
                    )
                )
            },
        )


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

    roles_path: list[Path | RepoRoleConfig] = []
    repo_staging: dict[Repo, Path] = {}
    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()

    @classmethod
    def from_merge(cls, *configs: Self) -> Self:
        if not configs:
            raise ValueError("Require at least one config")

        roles_path = list(
            itertools.chain.from_iterable(config.roles_path for config in configs)
        )
        repo_staging = dict(ChainMap(*(config.repo_staging for config in configs)))
        ansible_playbook = AnsiblePlaybookCommandConfig.from_merge(
            *(config.ansible_playbook for config in configs)
        )

        return cls(
            roles_path=roles_path,
            repo_staging=repo_staging,
            ansible_playbook=ansible_playbook,
        )

    def expand_roles_path(self) -> list[Path]:
        paths = []
        for role_path in self.roles_path:
            match role_path:
                case Path():
                    path = role_path.resolve()
                case RepoRoleConfig():
                    # TODO: implement it
                    raise NotImplementedError

            paths.append(path)

        return paths


class LocalRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class LocalRunnerInputConfig(LocalRunnerConfig):
    model_config = ConfigDict(frozen=True)

    ansible: AnsibleConfig = AnsibleConfig()


class DockerRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_name: str = ""  # TODO: fill roly by default
    # dockerfile: Path = ""  # TODO: Should we support it?  # noqa: ERA001
    workspace_dir: Path = Path("/home/ubuntu/workspace")
    roly_venv_dir: Path = Path("/home/ubuntu/app")
    extra_args: list[str] = []

    host_roly_src_dir: Path | None = None


class DockerRunnerInputConfig(DockerRunnerConfig):
    model_config = ConfigDict(frozen=True)

    ansible: AnsibleConfig = AnsibleConfig()


class RunnerInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    local: LocalRunnerInputConfig = LocalRunnerInputConfig()
    docker: DockerRunnerInputConfig = DockerRunnerInputConfig()


class RunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    local: LocalRunnerConfig = LocalRunnerConfig()
    docker: DockerRunnerConfig = DockerRunnerConfig()

    @classmethod
    def from_input_config(cls, config: RunnerInputConfig) -> Self:
        return cls.model_validate(
            {
                "local": {
                    key: value
                    for key, value in config.local.model_dump().items()
                    if key != "ansible"
                },
                "docker": {
                    key: value
                    for key, value in config.docker.model_dump().items()
                    if key != "ansible"
                },
            }
        )


class RolyInputConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env"],
        env_file_encoding="utf-8",
        yaml_file=["roly.yaml", "roly_local.yaml"],
    )

    base_dir: list[Path] = [Path("test/roly")]
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerInputConfig = RunnerInputConfig()
    given: TestCaseGiven = TestCaseGiven()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


class RolyConfig(BaseModel):
    base_dir: list[Path] = [Path("test/roly")]
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerConfig = RunnerConfig()
    given: TestCaseGiven = TestCaseGiven()

    @classmethod
    def from_input_config(cls, input_config: RolyInputConfig) -> Self:
        runner_mode = input_config.runner_mode

        match runner_mode:
            case RunnerMode.Docker:
                ansible_runner_config = input_config.runner.docker.ansible
            case RunnerMode.Local:
                ansible_runner_config = input_config.runner.local.ansible
        ansible = AnsibleConfig.from_merge(input_config.ansible, ansible_runner_config)

        runner = RunnerConfig.from_input_config(input_config.runner)

        return cls(
            base_dir=input_config.base_dir,
            runner_mode=input_config.runner_mode,
            ansible=ansible,
            runner=runner,
            given=input_config.given,
        )


def _init_input_config(
    base_path: list[Path] | None = None, config_path: Path | None = None
) -> RolyInputConfig:
    if config_path:
        path = config_path
    elif raw_path := os.environ.get(ROLY_CONFIG_PATH_ENV_NAME):
        path = Path(raw_path).expanduser().resolve()

    input_config = (
        RolyInputConfig.model_validate(yaml.safe_load(path.read_text()))
        if path
        else RolyInputConfig()
    )
    if base_path:
        input_config = input_config.model_copy(update={"base_dir": base_path})

    return input_config


def init_config(
    base_path: list[Path] | None = None, config_path: Path | None = None
) -> RolyConfig:
    return RolyConfig.from_input_config(_init_input_config(base_path, config_path))
