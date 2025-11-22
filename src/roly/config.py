from __future__ import annotations

import itertools
import logging
import os
from collections import ChainMap
from enum import Enum
from pathlib import Path
from typing import NewType, Self

from pydantic import BaseModel, ConfigDict

from roly.consts import ROLY_CONFIG_PATH_ENV_NAME, ROLY_LOCAL_CONFIG_PATH_ENV_NAME
from roly.test_case import TestCaseGiven

logger = logging.getLogger(__name__)


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
    playbooks_path: list[Path | RepoPlaybookConfig] = []
    repo_staging: dict[Repo, Path] = {}
    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()

    @classmethod
    def from_merge(cls, *configs: Self) -> Self:
        if not configs:
            raise ValueError("Require at least one config")

        roles_path = itertools.chain.from_iterable(
            config.roles_path for config in configs
        )
        playbooks_path = itertools.chain.from_iterable(
            config.playbooks_path for config in configs
        )
        repo_staging = dict(ChainMap(*(config.repo_staging for config in configs)))
        ansible_playbook = AnsiblePlaybookCommandConfig.from_merge(
            *(config.ansible_playbook for config in configs)
        )

        return cls.model_validate(
            {
                "roles_paths": list(roles_path),
                "playbooks_path": list(playbooks_path),
                "repo_staging": repo_staging,
                "ansible_playbook": ansible_playbook,
            },
        )


class LocalRunnerConfig:
    model_config = ConfigDict(frozen=True)


class LocalRunnerInputConfig(LocalRunnerConfig):
    model_config = ConfigDict(frozen=True)

    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()


class DockerRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_name: str = ""  # TODO: fill roly by default
    # dockerfile: Path = ""  # TODO: Should we support it?  # noqa: ERA001
    workspace_dir: Path = Path("/home/ubuntu/workspace")
    extra_args: list[str] = []


class DockerRunnerInputConfig(DockerRunnerConfig):
    model_config = ConfigDict(frozen=True)

    ansible_playbook: AnsiblePlaybookCommandConfig = AnsiblePlaybookCommandConfig()


class RunnerInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    local: LocalRunnerInputConfig | None = None
    docker: DockerRunnerInputConfig | None = None


class RunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    local: LocalRunnerConfig | None = None
    docker: DockerRunnerConfig | None = None


class RolyInputConfig(BaseModel):
    base_dir: list[Path] = [Path("test/roly")]
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerInputConfig = RunnerInputConfig()
    given: TestCaseGiven = TestCaseGiven()

    @classmethod
    def from_path(
        cls, configs_path: list[Path] | None, base_path: list[Path] | None = None
    ) -> Self:
        if not configs_path:
            logger.info("Config path does not exist. Use the default config")
            input_config = cls()
        else:
            logger.debug("Load config from path: %s", configs_path)
            inputs_config = [
                cls.model_validate(config_path) for config_path in configs_path
            ]
            # TODO: merge inputs_config

        if base_path:
            input_config = input_config.model_copy(update={"base_dir": base_path})

        return input_config

    @classmethod
    def from_merge(cls, *configs: Self) -> Self:
        raise NotImplementedError


class RolyConfig(BaseModel):
    base_dir: list[Path] = [Path("test/roly")]
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerConfig = RunnerConfig()


def _list_config_path(env_name: str, default_filename: str) -> Path | None:
    if raw_path := os.environ.get(env_name):
        return Path(raw_path)
    if (path := Path.cwd() / default_filename).exists():
        return path

    return None


def _search_config_path(configs_path: list[Path] | None = None) -> list[Path]:
    if configs_path:
        return configs_path

    return [
        path
        for env_name, default_filename in (
            (ROLY_CONFIG_PATH_ENV_NAME, "roly.yaml"),
            (ROLY_LOCAL_CONFIG_PATH_ENV_NAME, "roly_local.yaml"),
        )
        if (path := _list_config_path(env_name, default_filename))
    ]


def init_config(
    configs_path: list[Path] | None, base_path: list[Path] | None = None
) -> RolyConfig:
    configs_path = _search_config_path(configs_path)
    input_config = RolyInputConfig.from_path(configs_path, base_path)

    raise NotImplementedError
