from __future__ import annotations

import itertools
import logging
import os
from collections import ChainMap
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlparse

import yaml
from pydantic import AnyUrl, BaseModel, ConfigDict, ValidationError, WrapValidator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from yako.consts import YAKO_CONFIG_PATH_ENV_NAME
from yako.test_case import TestCaseGiven

if TYPE_CHECKING:
    from typing import Any, Self

logger = logging.getLogger(__name__)


type Repo = AnyUrl


class RunnerMode(Enum):
    Docker = "docker"
    Local = "local"


class AnsiblePlaybookCommandConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    verbose: bool = True
    connection: str = "local"
    inventory: str = "127.0.0.1,"
    limit: str = "127.0.0.1"
    ansible_stdout_callback: str = "debug"
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
            "ansible_stdout_callback": "debug",
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


class GitUri(BaseModel):
    netloc: str
    path: str
    uri: str
    cache_key: str = ""

    @classmethod
    def from_raw(cls, uri: str) -> Self:
        if uri.startswith("http"):
            result = urlparse(uri)
            return cls(netloc=result.netloc, path=result.path, uri=uri)
        if uri.startswith("git@") and ":" in uri:
            _, _, base = uri.partition("@")
            netloc, _, path = base.partition(":")
            return cls(netloc=netloc, path=path, uri=uri)

        msg = f"Not support for the git uri: {uri}"
        raise ValidationError(msg)

    def model_post_init(self, context: Any, /) -> None:
        object.__setattr__(self, "cache_key", f"{self.netloc}/{self.path}")

        return super().model_post_init(context)


def validate_git_uri(value, handler) -> GitUri:
    if isinstance(value, str):
        return GitUri.from_raw(value)

    return handler(value)


type ParsedGitUri = Annotated[GitUri, WrapValidator(validate_git_uri)]


class RepoRoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo: ParsedGitUri
    path: str = "roles"


class AnsibleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    roles_path: list[Path | RepoRoleConfig] = []
    repo_staging: dict[ParsedGitUri, Path] = {}
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


class LocalRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)


class LocalRunnerInputConfig(LocalRunnerConfig):
    model_config = ConfigDict(frozen=True)

    ansible: AnsibleConfig = AnsibleConfig()


class DockerRunnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_name: str = "ghcr.io/birnevogel11/yako:latest"
    # dockerfile: Path = ""  # TODO: Should we support it?  # noqa: ERA001
    workspace_dir: Path = Path("/home/ubuntu/workspace")
    yako_venv_dir: Path = Path("/home/ubuntu/app")
    yako_src_dir: Path = Path("/home/ubuntu/yako/src/yako")
    extra_args: list[str] = []

    ansible_playbook_bin: Path = Path("/home/ubuntu/app/bin/ansible-playbook")

    host_yako_repo_dir: Path | None = None

    def model_post_init(self, context: Any, /) -> None:
        object.__setattr__(
            self,
            "ansible_playbook_bin",
            self.yako_venv_dir / "bin" / "ansible-playbook",
        )
        if self.host_yako_repo_dir:
            object.__setattr__(
                self,
                "host_yako_repo_dir",
                self.host_yako_repo_dir.expanduser().resolve(),
            )

        return super().model_post_init(context)


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


class YakoInputConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env"],
        env_file_encoding="utf-8",
        yaml_file=["yako.yaml", "yako_local.yaml"],
    )

    base_dir: list[Path] = [Path("tests/yako")]
    runner_mode: RunnerMode = RunnerMode.Local
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


class YakoConfig(BaseModel):
    base_dir: list[Path] = [Path("tests/yako")]
    runner_mode: RunnerMode = RunnerMode.Docker
    ansible: AnsibleConfig = AnsibleConfig()
    runner: RunnerConfig = RunnerConfig()
    given: TestCaseGiven = TestCaseGiven()

    @classmethod
    def from_input_config(cls, input_config: YakoInputConfig) -> Self:
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
) -> YakoInputConfig:
    path = None
    if config_path:
        path = config_path
    elif raw_path := os.environ.get(YAKO_CONFIG_PATH_ENV_NAME):
        path = Path(raw_path)

    input_config = (
        YakoInputConfig.model_validate(
            yaml.safe_load(path.expanduser().resolve().read_text())
        )
        if path
        else YakoInputConfig()
    )
    if base_path:
        input_config = input_config.model_copy(update={"base_dir": base_path})

    return input_config


def init_config(
    base_path: list[Path] | None = None, config_path: Path | None = None
) -> YakoConfig:
    return YakoConfig.from_input_config(_init_input_config(base_path, config_path))
