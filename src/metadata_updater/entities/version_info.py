from dataclasses import dataclass

from pendulum.datetime import DateTime


@dataclass
class VersionInfo:
    version: str
    python_constraint: str
    released_at: DateTime
    yanked: bool
    dependencies: list[str]
