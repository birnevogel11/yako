from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from yako.assert_check import AssertMode, FileMode

if TYPE_CHECKING:
    from typing import Any


class _YakoDumper(yaml.dumper.SafeDumper):
    pass


yaml.add_representer(
    type(Path()),
    lambda dumper, obj: dumper.represent_scalar("tag:yaml.org,2002:str", str(obj)),
    _YakoDumper,
)
yaml.add_representer(
    AssertMode,
    lambda dumper, obj: dumper.represent_scalar("tag:yaml.org,2002:str", obj.value),
    _YakoDumper,
)
yaml.add_representer(
    FileMode,
    lambda dumper, obj: dumper.represent_scalar("tag:yaml.org,2002:str", obj.value),
    _YakoDumper,
)


def safe_dump(data: Any) -> str:
    """Safely dump data to a YAML string."""
    return yaml.dump(
        data,
        Dumper=_YakoDumper,
        sort_keys=False,
        indent=2,
    )
