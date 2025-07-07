import re
import shutil
from pathlib import Path

class Game:
    def __init__(self, directory: Path, titles: dict):
        self.dir = directory
        match = re.match(r"(.+)\[(.+)\]", directory.name)
        if not match:
            raise ValueError("Invalid game directory")
        self.title, self.id = match.groups()
        self.size = self._calc_size(directory)
        self.display_title = titles.get(self.id, self.title)
        self.checked = False

    def _calc_size(self, path: Path) -> int:
        total = 0
        for p in path.rglob('*'):
            if p.is_file():
                total += p.stat().st_size
        return total

    def delete(self):
        shutil.rmtree(self.dir, ignore_errors=True)
