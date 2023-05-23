from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from cleo.application import Application as BaseApplication
from cleo.loaders.factory_command_loader import FactoryCommandLoader

from metadata_updater.__version__ import __version__

if TYPE_CHECKING:
    from collections.abc import Callable

    from cleo.commands.command import Command


def load_command(name: str) -> Callable[[], Command]:
    def _load() -> Command:
        words = name.split(" ")
        module = import_module("metadata_updater.console.commands." + ".".join(words))
        command_class = getattr(module, "".join(c.title() for c in words) + "Command")
        command: Command = command_class()
        return command

    return _load


COMMANDS: list[str] = ["update package", "update all"]


class Application(BaseApplication):
    def __init__(self) -> None:
        super().__init__("metadata-updater", __version__)

        command_loader = FactoryCommandLoader(
            {name: load_command(name) for name in COMMANDS}
        )
        self.set_command_loader(command_loader)


def main() -> None:
    app = Application()

    return app.run()
