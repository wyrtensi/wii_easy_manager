#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A simplified redesigned Wii Unified Manager with a light kid-friendly interface."""

import sys
import threading
from pathlib import Path
from typing import List

import requests
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QLineEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
)

from wii_game_parser import WiiGameParser, WiiGameDatabase, WiiGame
from wii_game_downloader import WiiGameDownloader
from wii_download_manager.models.enhanced_drive import EnhancedDrive as Drive, CopyProgress
from wii_download_manager.models.game import Game as FlashGame


WII_STYLE = """
QMainWindow {
    background: #F0F5FC;
    font-family: 'Segoe UI', 'Arial';
    font-size: 11pt;
}
QPushButton {
    background: #FFFFFF;
    border: 2px solid #4A90E2;
    border-radius: 10px;
    padding: 6px 12px;
}
QPushButton:hover {
    background: #B3D9FF;
}
QLineEdit {
    background: #FFFFFF;
    border: 2px solid #E9ECEF;
    border-radius: 8px;
    padding: 6px 10px;
}
QListWidget {
    background: #FFFFFF;
    border: 2px solid #E9ECEF;
    border-radius: 8px;
}
QGroupBox {
    border: 2px solid #E9ECEF;
    border-radius: 8px;
    margin-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}
"""


class ImageLoader(QThread):
    image_loaded = Signal(QPixmap, QLabel)

    def __init__(self, url: str, label: QLabel):
        super().__init__()
        self.url = url
        self.label = label

    def run(self):
        pixmap = QPixmap()
        try:
            r = requests.get(self.url, timeout=10)
            if r.status_code == 200:
                pixmap.loadFromData(r.content)
        except Exception:
            pass
        self.image_loaded.emit(pixmap, self.label)


class GameCard(QWidget):
    def __init__(self, game: WiiGame, parent=None):
        super().__init__(parent)
        self.game = game
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(game.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-size:14pt;font-weight:bold;color:#4A90E2")
        layout.addWidget(title)

        self.box = QLabel()
        self.box.setFixedSize(200, 250)
        self.box.setStyleSheet("background:#E9ECEF;border-radius:8px")
        layout.addWidget(self.box)

        info = QLabel(
            f"Регион: {game.region}\nРейтинг: {game.rating}\nРазмер: {game.file_size}"
        )
        info.setStyleSheet("background:#FFFFFF;border-radius:6px;padding:6px")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.download_btn = QPushButton("Скачать")
        layout.addWidget(self.download_btn)

        if game.box_art:
            loader = ImageLoader(game.box_art, self.box)
            loader.image_loaded.connect(self.set_image)
            loader.start()
        else:
            self.box.setText("Нет изображения")

    def set_image(self, pix: QPixmap, label: QLabel):
        if not pix.isNull():
            label.setPixmap(pix.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            label.setText("Ошибка")


class WiiUnifiedManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wii Unified Manager (Redesign)")
        self.resize(1000, 700)
        self.setStyleSheet(WII_STYLE)

        self.parser = WiiGameParser()
        self.database = WiiGameDatabase()
        self.downloader = WiiGameDownloader()
        self.current_drive = None

        self.online_games: List[WiiGame] = []
        self.downloaded_games: List[Path] = []
        self.flash_games: List[FlashGame] = []

        self.init_ui()
        self.refresh_downloaded_games()
        self.refresh_drives()
        self.refresh_flash_games()

    # UI SETUP
    def init_ui(self):
        self.games_tabs = QTabWidget()
        self.setCentralWidget(self.games_tabs)

        self.search_page = self.create_search_page()
        self.manager_page = self.create_manager_page()

        self.games_tabs.addTab(self.search_page, "Поиск")
        self.games_tabs.addTab(self.manager_page, "Загрузки")

    def create_search_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_btn = QPushButton("Найти")
        self.search_btn.clicked.connect(self.perform_search)
        top.addWidget(self.search_input)
        top.addWidget(self.search_btn)
        layout.addLayout(top)

        body = QHBoxLayout()
        self.online_games_list = QListWidget()
        self.online_games_list.itemClicked.connect(self.on_game_selected)
        body.addWidget(self.online_games_list, 30)

        self.card_area = QVBoxLayout()
        self.card_layout = QVBoxLayout()
        self.card_area.addLayout(self.card_layout)
        body.addLayout(self.card_area, 70)
        layout.addLayout(body)

        self.download_panel = QProgressBar()
        self.download_panel.setValue(0)
        self.download_panel.hide()
        layout.addWidget(self.download_panel)

        return page

    def create_manager_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        drive_bar = QHBoxLayout()
        self.drive_btn = QPushButton("Выбрать флешку")
        self.drive_btn.clicked.connect(self.choose_drive)
        self.flash_panel = QPushButton("Обновить игры на флешке")
        self.flash_panel.clicked.connect(self.refresh_flash_games)
        drive_bar.addWidget(self.drive_btn)
        drive_bar.addWidget(self.flash_panel)
        layout.addLayout(drive_bar)

        lists = QHBoxLayout()
        self.downloaded_games_list = QListWidget()
        self.downloaded_games_list.itemClicked.connect(self.on_downloaded_selected)
        lists.addWidget(self.downloaded_games_list, 30)

        self.flash_games_list = QListWidget()
        self.flash_games_list.itemClicked.connect(self.on_flash_selected)
        lists.addWidget(self.flash_games_list, 30)

        self.manager_card = QVBoxLayout()
        lists.addLayout(self.manager_card, 40)
        layout.addLayout(lists)

        return page

    # NAVIGATION
    def show_search_section(self):
        self.games_tabs.setCurrentWidget(self.search_page)

    def show_manager_section(self):
        self.games_tabs.setCurrentWidget(self.manager_page)

    # SEARCH
    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.online_games_list.clear()
        thread = SearchThread(self.parser, query)
        thread.results_ready.connect(self.display_online_games)
        thread.start()

    def display_online_games(self, games: List[WiiGame]):
        self.online_games = games
        for game in games:
            item = QListWidgetItem(f"{game.title} ({game.region})")
            item.setData(Qt.UserRole, game)
            self.online_games_list.addItem(item)

    def on_game_selected(self, item: QListWidgetItem):
        game = item.data(Qt.UserRole)
        self.show_game_card(game)

    def show_game_card(self, game: WiiGame):
        for i in reversed(range(self.card_layout.count())):
            w = self.card_layout.takeAt(i).widget()
            if w:
                w.deleteLater()
        card = GameCard(game)
        card.download_btn.clicked.connect(lambda: self.download_game(game))
        self.card_layout.addWidget(card)

    # DOWNLOAD
    def download_game(self, game: WiiGame):
        info = self.downloader.get_download_info(game.detail_url)
        if not info.get('download_url'):
            QMessageBox.warning(self, "Ошибка", "Ссылка не найдена")
            return
        filename = self.downloader.generate_filename(game.title, game.region)
        self.download_panel.show()
        self.download_panel.setValue(0)
        self.download_thread = DownloadThread(info['download_url'], filename, self.downloader)
        self.download_thread.progress.connect(self.download_panel.setValue)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def on_download_finished(self, ok: bool, path: str):
        self.download_panel.hide()
        if ok:
            QMessageBox.information(self, "Загрузка", f"Файл сохранен: {path}")
            self.refresh_downloaded_games()
        else:
            QMessageBox.warning(self, "Ошибка загрузки", path)

    # MANAGER FUNCTIONS
    def refresh_downloaded_games(self):
        self.downloaded_games_list.clear()
        downloads = Path("downloads")
        downloads.mkdir(exist_ok=True)
        for file in downloads.glob("*.wbfs"):
            item = QListWidgetItem(file.name)
            item.setData(Qt.UserRole, file)
            self.downloaded_games_list.addItem(item)

    def refresh_drives(self):
        drives = Drive.get_drives()
        if drives:
            self.current_drive = drives[0]
            self.drive_btn.setText(f"{self.current_drive.name} ({self.current_drive.available_space} ГБ свободно)")

    def choose_drive(self):
        drives = Drive.get_drives()
        if not drives:
            QMessageBox.information(self, "Нет флешек", "Флешки не найдены")
            return
        menu = QMenu()
        for d in drives:
            act = QAction(d.name, self)
            act.triggered.connect(lambda checked, dr=d: self.set_drive(dr))
            menu.addAction(act)
        menu.exec(self.drive_btn.mapToGlobal(self.drive_btn.rect().bottomLeft()))

    def set_drive(self, drive):
        self.current_drive = drive
        self.drive_btn.setText(f"{drive.name} ({drive.available_space} ГБ свободно)")
        self.refresh_flash_games()

    def refresh_flash_games(self):
        self.flash_games_list.clear()
        if not self.current_drive:
            return
        try:
            self.flash_games = self.current_drive.get_games()
            for g in self.flash_games:
                item = QListWidgetItem(g.display_title)
                item.setData(Qt.UserRole, g)
                self.flash_games_list.addItem(item)
        except Exception:
            pass

    def on_downloaded_selected(self, item: QListWidgetItem):
        file_path = item.data(Qt.UserRole)
        self.show_file_card(file_path)

    def on_flash_selected(self, item: QListWidgetItem):
        game = item.data(Qt.UserRole)
        self.show_flash_game_card(game)

    def show_file_card(self, file_path: Path):
        for i in reversed(range(self.manager_card.count())):
            w = self.manager_card.takeAt(i).widget()
            if w:
                w.deleteLater()
        label = QLabel(file_path.name)
        label.setStyleSheet("font-size:14pt")
        self.manager_card.addWidget(label)
        install = QPushButton("Установить на флешку")
        install.clicked.connect(lambda: self.install_game_to_flash(file_path))
        self.manager_card.addWidget(install)

    def show_flash_game_card(self, game: FlashGame):
        for i in reversed(range(self.manager_card.count())):
            w = self.manager_card.takeAt(i).widget()
            if w:
                w.deleteLater()
        label = QLabel(game.display_title)
        label.setStyleSheet("font-size:14pt")
        self.manager_card.addWidget(label)
        remove = QPushButton("Удалить с флешки")
        remove.clicked.connect(lambda: self.remove_game_from_flash(game))
        self.manager_card.addWidget(remove)

    def install_selected_to_flash(self):
        item = self.downloaded_games_list.currentItem()
        if item:
            self.install_game_to_flash(item.data(Qt.UserRole))

    def install_game_to_flash(self, file_path: Path):
        if not self.current_drive:
            QMessageBox.warning(self, "Флешка", "Не выбрана флешка")
            return
        self.copy_thread = CopyThread(self.current_drive, [str(file_path)])
        self.copy_thread.finished.connect(self.on_copy_finished)
        self.copy_thread.start()

    def on_copy_finished(self, ok: bool, msg: str):
        if ok:
            QMessageBox.information(self, "Успех", msg)
            self.refresh_flash_games()
        else:
            QMessageBox.warning(self, "Ошибка", msg)

    def delete_downloaded_game(self):
        item = self.downloaded_games_list.currentItem()
        if item:
            path = item.data(Qt.UserRole)
            path.unlink(missing_ok=True)
            self.refresh_downloaded_games()

    def add_external_games(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите игры", "", "Game files (*.wbfs *.iso *.rvz)")
        if files:
            self.install_games(files)

    def install_games(self, files: List[str]):
        if not self.current_drive:
            return
        self.copy_thread = CopyThread(self.current_drive, files)
        self.copy_thread.finished.connect(self.on_copy_finished)
        self.copy_thread.start()

    def remove_from_flash(self):
        item = self.flash_games_list.currentItem()
        if item:
            self.remove_game_from_flash(item.data(Qt.UserRole))

    def remove_game_from_flash(self, game: FlashGame):
        try:
            game.delete()
        except Exception:
            pass
        self.refresh_flash_games()


class SearchThread(QThread):
    results_ready = Signal(list)

    def __init__(self, parser: WiiGameParser, query: str):
        super().__init__()
        self.parser = parser
        self.query = query

    def run(self):
        try:
            games = self.parser.search_games_online(self.query)
        except Exception:
            games = []
        self.results_ready.emit(games)


class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, url: str, filename: str, downloader: WiiGameDownloader):
        super().__init__()
        self.url = url
        self.filename = filename
        self.downloader = downloader

    def run(self):
        def cb(downloaded, total):
            if total > 0:
                self.progress.emit(int((downloaded / total) * 100))
        try:
            ok = self.downloader.download_game(self.url, self.filename, cb)
            path = str(Path(self.downloader.download_dir) / self.filename)
            self.finished.emit(ok, path)
        except Exception as e:
            self.finished.emit(False, str(e))


class CopyThread(QThread):
    finished = Signal(bool, str)

    def __init__(self, drive: Drive, files: List[str]):
        super().__init__()
        self.drive = drive
        self.files = files

    def run(self):
        try:
            self.drive.add_games_with_progress([Path(f) for f in self.files])
            self.finished.emit(True, "Файлы скопированы")
        except Exception as e:
            self.finished.emit(False, str(e))


def main():
    app = QApplication(sys.argv)
    win = WiiUnifiedManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
