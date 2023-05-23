from cleo.commands.command import Command
from cleo.helpers import argument


class UpdatePackageCommand(Command):
    name = "update package"

    arguments = [argument("package")]

    def handle(self) -> int:
        from pathlib import Path

        from metadata_updater.updater import Updater

        with Updater(Path.cwd(), io=self._io) as updater:
            updater.update(self.argument("package"), "*")

        return 0
