from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from typing import Any


class _PathDumper(yaml.dumper.SafeDumper):
    pass


yaml.add_representer(
    type(Path()),
    lambda dumper, obj: dumper.represent_scalar("tag:yaml.org,2002:str", str(obj)),
    _PathDumper,
)


def safe_dump(data: Any) -> str:
    """Safely dump data to a YAML string."""
    return yaml.dump(
        data,
        Dumper=_PathDumper,
        sort_keys=False,
        indent=2,
    )
