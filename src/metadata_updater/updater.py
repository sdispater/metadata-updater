from __future__ import annotations

import json
import logging
import operator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import pendulum
from cleo.io.null_io import NullIO
from cleo.ui.progress_bar import ProgressBar
from packaging.utils import canonicalize_name
from poetry.factory import Factory
from poetry.repositories.exceptions import PackageNotFound
from poetry.repositories.pypi_repository import PyPiRepository
from poetry.repositories.repository_pool import RepositoryPool
from tqdm import tqdm

from metadata_updater.changelog import Changelog
from metadata_updater.entities.package_info import PackageInfo
from metadata_updater.entities.version_info import VersionInfo

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Self

    from cleo.io.io import IO


class Encoder(json.JSONEncoder):
    def default(self, obj) -> str:
        from pendulum.datetime import DateTime

        if isinstance(obj, DateTime):
            return obj.isoformat()

        return super().default(obj)


class SimplePageParser(HTMLParser):
    def __init__(self, *, convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)

        self.packages = []
        self._parsing_tag = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._parsing_tag = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._parsing_tag = False

    def handle_data(self, data: str) -> None:
        if self._parsing_tag:
            self.packages.append(data.strip())


class Updater:
    def __init__(self, destination: Path, *, io: IO | None = None) -> None:
        self._destination = destination
        self._serials_path = destination.joinpath("metadata").joinpath("serials.json")
        self._serials = None
        self._changelog = Changelog()
        self._io = io or NullIO()
        self._pool = RepositoryPool()
        self._repository = PyPiRepository()
        self._pool.add_repository(self._repository)

    @property
    def serials(self) -> dict[str]:
        if self._serials is None:
            if self._serials_path.exists():
                self._serials = json.loads(self._serials_path.read_text())
            else:
                self._serials = {}

        return self._serials

    def full_update(
        self,
        ignore_serials: bool = False,
        limit: int | None = None,
        concurrency: int = 10,
    ) -> None:
        logging.disable(logging.WARNING)

        self._io.write_line(f"Executing full update")

        if ignore_serials or not self.serials:
            updated_packages = list(sorted(self._changelog.serials().keys()))
        else:
            current_serials = sorted(
                self._changelog.serials().items(), key=operator.itemgetter(1)
            )
            updated_packages = [
                name
                for name, serial in current_serials
                if self.serials.get(name) != serial
            ]

        if limit:
            updated_packages = updated_packages[:limit]

        total = len(updated_packages)
        padding = len(str(total))

        self._io.write_line(f"Updating {total} packages")

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            iterator = executor.map(lambda p: self.update(p, "*"), updated_packages)

            for _ in tqdm(iterator, total=total):
                continue

        return 0

    def update(self, package_name: str, constraint: str) -> int:
        package_name = canonicalize_name(package_name)
        # self._io.write_line(
        #    f"Updating metadata for package <info>{package_name}</> for versions matching constraint <comment>{constraint}</>"
        # )

        try:
            packages = self._pool.find_packages(
                Factory.create_dependency(package_name, constraint)
            )
        except PackageNotFound:
            # self._io.write_error_line("  <error>✕</> No packages found")
            return

        packages.sort(key=lambda p: p.version, reverse=True)
        subdir = package_name[0]
        if len(package_name) > 1:
            subdir += "/" + package_name[1]

        metadata_dir = self._destination.joinpath("metadata").joinpath(subdir)
        metadata_path = metadata_dir.joinpath(f"{package_name}.json")

        json_info = self._repository._get(f"/pypi/{package_name}/json")
        if json_info is None:
            serial = 0
        else:
            serial = json_info["last_serial"]

        versions = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            for version, version_info in metadata["versions"].items():
                versions[version] = VersionInfo(**version_info)

        for pkg in packages:
            version = pkg.version
            try:
                releases = json_info["releases"][pkg.pretty_version]
            except KeyError:
                if pkg.version.is_postrelease():
                    try:
                        releases = json_info["releases"][
                            pkg.version.without_postrelease().text
                        ]
                        version = pkg.version.without_postrelease()
                    except KeyError:
                        continue
                else:
                    continue

            try:
                pkg = self._pool.package(pkg.name, version)
            except Exception:
                continue

            if not releases:
                continue

            version_info = VersionInfo(
                version=pkg.pretty_version,
                python_constraint=pkg.python_versions,
                released_at=pendulum.parse(releases[0]["upload_time"]),
                yanked=pkg.yanked,
                dependencies=[],
            )

            for dep in sorted(pkg.requires, key=lambda dep: dep.name):
                version_info.dependencies.append(dep.to_pep_508())

            versions[version_info.version] = version_info

        package_info = PackageInfo(name=package_name, versions=versions)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        metadata_path.write_text(json.dumps(asdict(package_info), cls=Encoder))
        self.serials[package_name] = serial

        # self._io.write_line("  <fg=green>✓</> Metadata updated")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args) -> None:
        self._serials_path.write_text(json.dumps(self.serials))
