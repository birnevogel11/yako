from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

from diskcache import Cache
from git import Repo
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime

from yako.config import GitUri, RepoRoleConfig, init_config

logger = logging.getLogger(__name__)


class RepoCacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    uri: GitUri
    path: Path
    init_time: NaiveDatetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    last_pull_time: NaiveDatetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )

    def is_expired(self, update_secs: int) -> bool:
        update_time = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(
            seconds=update_secs
        )
        return self.last_pull_time >= update_time


class RepoCache:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = Path("~/.cache/yako").expanduser()
        self._repo_base_dir: Path = None  # type: ignore[assignment]
        self._cache: Cache = None
        self._is_init = False

    def init(self) -> None:
        if self._is_init:
            return

        if raw_path := os.environ.get("YAKO_REPO_CACHE_DIR"):
            self._base_dir = Path(raw_path).expanduser().resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._repo_base_dir = self._base_dir / "repos"
        self._repo_base_dir.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(self._base_dir / "yako_cache_db")

        self.is_init = True

    def query(self, uri: GitUri) -> RepoCacheEntry | None:
        if not self._is_init:
            self.init()

        if entry := self._cache.get(uri.cache_key):
            return RepoCacheEntry.model_validate_json(entry)
        return None

    def add(self, uri: GitUri) -> RepoCacheEntry:
        if not self._is_init:
            self.init()

        if entry := self.query(uri):
            logger.warning(
                "The Git repo cache exists. Skip to add it again. uri: %s",
                uri.cache_key,
            )
            return entry

        cache_path = self._repo_base_dir / uri.cache_key
        logger.info(
            "Add a new git repo cache. repo: %s, path: %s", uri.cache_key, cache_path
        )

        # Clone the repo to the cache path
        Repo.clone_from(uri.uri, str(cache_path))
        entry = RepoCacheEntry(uri=uri, path=cache_path)

        self._cache.add(uri.cache_key, entry.model_dump_json())
        return entry

    def pull(self, uri: GitUri) -> RepoCacheEntry:
        if not self._is_init:
            self.init()

        if not (entry := self.query(uri)):
            logger.warning(
                "Fail to find git repo in cache. Add it now. repo: %s", uri.cache_key
            )
            entry = self.add(uri)

        logger.info("Update git repo cache: %s, path: %s", uri.cache_key, entry.path)
        repo = Repo(entry.path)
        repo.remote().pull()

        updated_entry = RepoCacheEntry(
            uri=entry.uri,
            path=entry.path,
            init_time=entry.init_time,
            last_pull_time=datetime.datetime.now(tz=datetime.UTC),
        )
        self._cache.add(updated_entry.uri.cache_key, updated_entry.model_dump_json())

        return updated_entry


class RepoPathResolver:
    def __init__(
        self, repo_staging: dict[GitUri, Path], repo_cache: RepoCache | None = None
    ) -> None:
        self._repo_cache = repo_cache or RepoCache()
        self._repo_staging = repo_staging

    def resolve(self, repo_uri: str | GitUri, update_secs: int | None = None) -> Path:
        """Resolve git uri to path.

        The resolver does not support branch for now.

        Input Patterns:
            git@github.com:birnevogel11/yako.git
            http://github.com/birnevogel11/yako.git
        """
        if isinstance(repo_uri, str):
            repo_uri = GitUri.from_raw(repo_uri)

        if path := self._repo_staging.get(repo_uri, None):
            return path

        if entry := self._repo_cache.query(repo_uri):
            if update_secs and entry.is_expired(update_secs):
                logger.info("Update git repo %s to latest ...", entry.uri.uri)
                entry = self._repo_cache.pull(entry.uri)

            return entry.path

        return self._repo_cache.add(repo_uri).path


def update_repo_cache(config_path: Path | None = None) -> None:
    config = init_config(config_path=config_path)

    repo_role_configs = [
        roles_config
        for roles_config in config.ansible.roles_path
        if isinstance(roles_config, RepoRoleConfig)
        and roles_config.repo not in config.ansible.repo_staging
    ]

    repo_cache = RepoCache()
    for repo_role_config in repo_role_configs:
        repo_cache.pull(repo_role_config.repo)
