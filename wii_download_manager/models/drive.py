import os
import re
import shutil
import requests
import psutil
from pathlib import Path
from .game import Game

TITLES_URL = "https://www.gametdb.com/titles.txt"

class Drive:
    def __init__(self, name: str, total_space: str, available_space: str, mount_point: Path):
        self.name = name
        self.total_space = total_space
        self.available_space = available_space
        self.mount_point = mount_point

    @staticmethod
    def get_drives():
        drives = []
        for part in psutil.disk_partitions(all=False):
            # heuristics: consider removable if path contains '/media' or 'removable'
            if 'removable' in part.opts or '/media' in part.mountpoint.lower() or '/run/media' in part.mountpoint.lower():
                usage = psutil.disk_usage(part.mountpoint)
                drives.append(
                    Drive(
                        name=os.path.basename(part.mountpoint) or part.device,
                        total_space=f"{usage.total / (1<<30):.2f}",
                        available_space=f"{usage.free / (1<<30):.2f}",
                        mount_point=Path(part.mountpoint),
                    )
                )
        return drives

    def _download_titles(self, path: Path) -> bool:
        """Try to download titles.txt. Returns True on success."""
        try:
            resp = requests.get(TITLES_URL, timeout=10)
            resp.raise_for_status()
        except Exception:
            return False
        try:
            with open(path, 'wb') as f:
                f.write(resp.content)
            return True
        except Exception:
            return False

    def _get_titles_map(self):
        path = self.mount_point / "titles.txt"
        if not path.exists():
            if not self._download_titles(path):
                return {}
        titles = {}
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        game_id, title = line.split('=', 1)
                        titles[game_id.strip()] = title.strip()
        except Exception:
            return {}
        return titles

    def get_games(self):
        wbfs_folder = self.mount_point / "wbfs"
        wbfs_folder.mkdir(exist_ok=True)
        titles = self._get_titles_map()
        games = []
        for entry in wbfs_folder.iterdir():
            if entry.is_dir():
                try:
                    games.append(Game(entry, titles))
                except Exception:
                    pass
        games.sort(key=lambda g: g.display_title)
        return games

    def add_game(self, file_path: Path):
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        wbfs_folder = self.mount_point / "wbfs"
        wbfs_folder.mkdir(exist_ok=True)
        match = re.match(r"(.+)\[(.+)\]", file_path.stem)
        if match:
            title, game_id = match.groups()
        else:
            game_id = self._read_game_id(file_path)
            title = file_path.stem
        if not game_id:
            raise ValueError("Could not determine game ID")
        dir_name = f"{title.strip()} [{game_id}]"
        dest_dir = wbfs_folder / dir_name
        dest_dir.mkdir(exist_ok=True)
        dest_file = dest_dir / f"{dir_name}.wbfs"
        shutil.copy2(file_path, dest_file)
        return dest_file

    def _read_game_id(self, path: Path) -> str | None:
        """Read the 6 byte game ID from an ISO or WBFS file."""
        try:
            with open(path, 'rb') as f:
                if path.suffix.lower() == '.wbfs':
                    f.seek(0x200)
                data = f.read(6)
                id = data.decode('ascii', errors='ignore').strip()
                return id if len(id) == 6 else None
        except Exception:
            return None
