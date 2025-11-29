from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from diskcache import Cache
from pydantic import BaseModel, Field, NaiveDatetime

if TYPE_CHECKING:
    from typing import Any, Self

logger = logging.getLogger(__name__)


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

        raise NotImplementedError

    def model_post_init(self, context: Any, /) -> None:
        object.__setattr__(self, "cache_key", f"{self.netloc}/{self.path}")

        return super().model_post_init(context)


class RepoCacheEntry(BaseModel):
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
        self._base_dir = Path("~/.cache/roly").expanduser()
        self._repo_base_dir: Path = None  # type: ignore[assignment]
        self._cache: Cache = None  # type: ignore[assignment]
        self._is_init = False

    def init(self) -> None:
        if self._is_init:
            return

        if raw_path := os.environ.get("ROLY_REPO_CACHE_DIR"):
            self._base_dir = Path(raw_path).expanduser().resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._repo_base_dir = self._base_dir / "repos"
        self._repo_base_dir.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(self._base_dir / "roly_cache_db")

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

        # TODO: git clone with gitpython

        self._cache.add(
            uri.cache_key,
            RepoCacheEntry(uri=uri, path=cache_path).model_dump_json(),
        )

        return cache_path


class RepoPathResolver:
    def __init__(self, repo_cache: RepoCache, repo_staging: dict[GitUri, Path]) -> None:
        self._repo_cache = repo_cache
        self._repo_staging = repo_staging

    def resolve(self, repo_uri: str | GitUri) -> Path:
        """Resolve git uri to path.

        The resolver does not support branch for now.

        Input Patterns:
            git@github.com:birnevogel11/roly.git
            http://github.com/birnevogel11/roly.git
        """
        if isinstance(repo_uri, str):
            repo_uri = GitUri.from_raw(repo_uri)

        if path := self._repo_staging.get(repo_uri, None):
            return path

        if path := self._repo_cache.query(repo_uri):
            return path

        return self._repo_cache.add(repo_uri)
