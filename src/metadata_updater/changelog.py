import xmlrpc.client

from packaging.utils import canonicalize_name


class Changelog:
    def __init__(self) -> None:
        self._client = xmlrpc.client.ServerProxy("https://pypi.org/pypi")

    def since_serial(self, serial: int) -> None:
        return self._client.changelog_since_serial(serial)

    def serials(self) -> dict[str, int]:
        return {
            canonicalize_name(name): serial
            for name, serial in self._client.list_packages_with_serial().items()
        }
