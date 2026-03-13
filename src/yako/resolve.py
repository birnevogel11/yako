from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from yako.config import RepoRoleConfig
from yako.repo import RepoPathResolver

if TYPE_CHECKING:
    from yako.config import AnsibleConfig


def resolve_roles_path(ansible_config: AnsibleConfig) -> list[Path]:
    repo_resolver = RepoPathResolver(ansible_config.repo_staging)

    paths = []
    for role_path in ansible_config.roles_path:
        match role_path:
            case Path():
                path = role_path.resolve()
            case RepoRoleConfig():
                repo_path = repo_resolver.resolve(role_path.repo)
                path = repo_path / role_path.path

        paths.append(path)

    return paths
