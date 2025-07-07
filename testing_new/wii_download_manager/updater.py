import webbrowser
import requests
from PySide6.QtWidgets import QMessageBox

APP_NAME = "TinyWiiBackupManager"
LATEST_RELEASE_URL = "https://api.github.com/repos/mq1/TinyWiiBackupManager/releases/latest"
RELEASES_BASE_URL = "https://github.com/mq1/TinyWiiBackupManager/releases/tag/"

__version__ = "0.3.11"


def check_for_updates(parent=None):
    try:
        resp = requests.get(LATEST_RELEASE_URL, timeout=10)
        resp.raise_for_status()
        latest = resp.json().get("tag_name")
        if latest and latest != __version__:
            res = QMessageBox.question(
                parent,
                "Update available",
                f"A new version of {APP_NAME} is available: {latest}.\nDo you want to download it?",
            )
            if res == QMessageBox.Yes:
                webbrowser.open(f"{RELEASES_BASE_URL}{latest}")
        else:
            QMessageBox.information(parent, "No updates", f"You are using the latest version of {APP_NAME}.")
    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Error checking updates: {e}")
