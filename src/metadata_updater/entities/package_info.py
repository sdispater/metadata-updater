from dataclasses import dataclass

from metadata_updater.entities.version_info import VersionInfo


@dataclass
class PackageInfo:
    name: str
    versions: VersionInfo
