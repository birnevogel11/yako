from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

from diskcache import Cache
from git import Repo
from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime

from yako.config import GitUri

logger = logging.getLogger(__name__)


class RepoCacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    uri: GitUri
    path: Path
    init_time: NaiveDatetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    update_time: NaiveDatetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )


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

    def query(self, uri: GitUri) -> Path | None:
        if not self._is_init:
            self.init()

        if entry := self._cache.get(uri.cache_key):
            return Path(RepoCacheEntry.model_validate_json(entry).path)
        return None

    def add(self, uri: GitUri) -> Path:
        if not self._is_init:
            self.init()

        if self.query(uri):
            logger.warning("The Git repo cache exists. Skip to add it again.")

        cache_path = self._repo_base_dir / uri.cache_key

        # Clone the repo to the cache path
        Repo.clone_from(uri.uri, str(cache_path))

        self._cache.add(
            uri.cache_key,
            RepoCacheEntry(uri=uri, path=cache_path).model_dump_json(),
        )

        return cache_path


class RepoPathResolver:
    def __init__(
        self, repo_staging: dict[GitUri, Path], repo_cache: RepoCache | None = None
    ) -> None:
        self._repo_cache = repo_cache or RepoCache()
        self._repo_staging = repo_staging

    def resolve(self, repo_uri: str | GitUri) -> Path:
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

        if path := self._repo_cache.query(repo_uri):
            return path

        return self._repo_cache.add(repo_uri)
