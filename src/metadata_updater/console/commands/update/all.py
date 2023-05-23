from pathlib import Path

from cleo.commands.command import Command
from cleo.helpers import option


class UpdateAllCommand(Command):
    name = "update all"

    options = [
        option("ignore-serials", flag=True),
        option("limit", flag=False, value_required=True),
    ]

    def handle(self) -> int:
        from metadata_updater.updater import Updater

        ignore_serials = self.option("ignore-serials")
        limit = None
        if self.option("limit"):
            limit = int(self.option("limit"))

        with Updater(Path.cwd(), io=self._io) as updater:
            updater.full_update(ignore_serials=ignore_serials, limit=limit)

        return 0
