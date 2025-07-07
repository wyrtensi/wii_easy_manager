#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wii Unified Manager 2.4
======================
Главный исполняемый файл приложения с новым Wii‑стилем, поиском онлайн игр и
загрузками. Требует:
  • wum_style.py          — палитра + QSS
  • download_queue.py     — очередь загрузок
  • wii_game_parser.py    — парсер страниц (из прежней версии)
  • wii_game_selenium_downloader.py — реальный загрузчик
"""

from __future__ import annotations

import sys
from pathlib import Path
import os # For path manipulation
from typing import List, Optional, Dict # Added Dict

# Adjust Python path to include project root for wii_download_manager
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtCore import (
    QEasingCurve,
    QObject, # Added for DownloadQueue
    QPropertyAnimation,
    QRectF,
    Qt,
    Slot,
    QThread, # Already here but good to note
    Signal,  # Already here
    QSize,   # Already here
    QTimer   # Already here
)
from PySide6.QtGui import (QIcon, QPixmap, QAction, 
) # Added QAction for menu actions
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QComboBox, # Added QComboBox
    QFileDialog, # Added QFileDialog for file dialogs
)
# from PySide6.QtCore import QThread, Signal, QSize, QTimer # Moved up

import base64 # For image loading
import requests # For image loading
import json # For database
import time # For download delay
from collections import deque # For the download queue

# ────────────────────────────────────────────────────────────────────────────
# Local modules
# ────────────────────────────────────────────────────────────────────────────
from wum_style import build_style, WII_BLUE, WII_GRAY, WII_WHITE, WII_LIGHT_GRAY, WII_LIGHT_BLUE, WII_GREEN, WII_DARK_GRAY # type: ignore
# from download_queue import DownloadQueue # type: ignore # Defined in this file
from wii_game_parser import WiiGame, WiiGameParser, WiiGameDatabase
from wii_game_selenium_downloader import WiiGameSeleniumDownloader
# Attempt to import EnhancedDrive, handle if module or its dependencies are missing
try:
    from wii_download_manager.models.enhanced_drive import EnhancedDrive as Drive
    from wii_download_manager.models.game import Game as FlashGame # Assuming this is used with EnhancedDrive
    ENHANCED_DRIVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: EnhancedDrive module not available, USB features will be limited. Error: {e}")
    Drive = None
    FlashGame = None
    ENHANCED_DRIVE_AVAILABLE = False


###############################################################################
# 📥 DownloadQueue                                                            #
###############################################################################

class DownloadQueue(QObject): # Inherit from QObject for signals
    """Manages a queue of games to download one by one."""
    queue_changed = Signal(int)  # Number of items in queue
    download_started = Signal(WiiGame)
    # Emits game, percentage (0-100), downloaded_bytes, total_bytes, speed_mbps (MB/s), eta_str
    progress_changed = Signal(WiiGame, int, float, float, float, str)
    download_finished = Signal(WiiGame) # Emits game (status will be updated)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._queue: deque[WiiGame] = deque()
        self._current_game: Optional[WiiGame] = None
        self._is_downloading: bool = False
        self._downloader: Optional[WiiGameSeleniumDownloader] = None
        self._download_worker_thread: Optional[QThread] = None # For Selenium

        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._process_next)
        self._DOWNLOAD_DELAY_MS = 10000 # 10 seconds

    def add(self, game: WiiGame):
        """Adds a game to the download queue."""
        if game not in self._queue and (not self._current_game or self._current_game.title != game.title):
            game.status = "queued"
            self._queue.append(game)
            self.queue_changed.emit(len(self._queue))
            print(f"[DownloadQueue] Added {game.title} to queue. Queue size: {len(self._queue)}")
            self._process_next() # Try to start if not already downloading

    def _process_next(self):
        if self._is_downloading or not self._queue:
            return

        self._is_downloading = True
        self._current_game = self._queue.popleft()
        self.queue_changed.emit(len(self._queue))

        if not self._current_game or not self._current_game.detail_url:
            print(f"[DownloadQueue] Error: Game {self._current_game.title if self._current_game else 'Unknown'} has no detail_url.")
            self._current_game.status = "error"
            self.download_finished.emit(self._current_game)
            self._is_downloading = False
            self._current_game = None
            self._delay_timer.start(self._DOWNLOAD_DELAY_MS) # Still delay before next attempt
            return

        self._current_game.status = "downloading"
        self.download_started.emit(self._current_game)
        print(f"[DownloadQueue] Starting download for: {self._current_game.title}")

        self._downloader = WiiGameSeleniumDownloader() # New instance for each download

        # Setup worker thread for selenium
        class SeleniumDownloadWorker(QObject):
            finished_signal = Signal(bool, str) # success, final_filepath_or_error_msg

            def __init__(self, downloader, game_url, game_title, progress_cb):
                super().__init__()
                self.downloader = downloader
                self.game_url = game_url
                self.game_title = game_title
                self.progress_cb = progress_cb
                self._should_stop = False

            @Slot()
            def run(self):
                success = self.downloader.download_game(
                    self.game_url,
                    self.game_title,
                    self.progress_cb,
                    lambda: self._should_stop # Pass stop check callable
                )
                if success:
                    downloaded_files = self.downloader.get_downloaded_files()
                    final_path = str(downloaded_files[0]) if downloaded_files else ""
                    self.finished_signal.emit(True, final_path)
                else:
                    self.finished_signal.emit(False, "Download failed or cancelled by SeleniumDownloader.")

            def request_stop(self):
                self._should_stop = True
                if self.downloader:
                    self.downloader.stop_download()


        self._download_worker_thread = QThread()
        self._selenium_worker = SeleniumDownloadWorker(
            self._downloader,
            self._current_game.detail_url,
            self._current_game.title,
            self._on_selenium_progress
        )
        self._selenium_worker.moveToThread(self._download_worker_thread)

        self._download_worker_thread.started.connect(self._selenium_worker.run)
        self._selenium_worker.finished_signal.connect(self._on_selenium_download_finished)
        # Ensure thread quits after work is done
        self._selenium_worker.finished_signal.connect(self._download_worker_thread.quit)
        self._download_worker_thread.finished.connect(self._download_worker_thread.deleteLater)
        self._selenium_worker.finished_signal.connect(self._selenium_worker.deleteLater)

        self._download_worker_thread.start()

    def _on_selenium_progress(self, downloaded_bytes: int, total_bytes: int, speed_mbps: float, eta_str: str):
        # This callback comes from WiiGameSeleniumDownloader's internal monitoring
        if self._current_game:
            percentage = 0
            if total_bytes > 0:
                percentage = int((downloaded_bytes / total_bytes) * 100)
            else:
                percentage = 0 # Or handle as indeterminate if total_bytes is unknown initially

            self.progress_changed.emit(self._current_game, percentage, downloaded_bytes, total_bytes, speed_mbps, eta_str)

    @Slot(bool, str)
    def _on_selenium_download_finished(self, success: bool, result_path_or_msg: str):
        print(f"[DownloadQueue] Selenium download finished for {self._current_game.title}. Success: {success}, Message: {result_path_or_msg}")
        if self._current_game: # Check if not cancelled while this signal was pending
            if success:
                self._current_game.status = "downloaded"
                self._current_game.local_path = result_path_or_msg # Store the actual path
            else:
                # Distinguish between user cancel and actual error if possible
                if self._downloader and self._downloader.should_stop: # If downloader was told to stop
                     self._current_game.status = "new" # Or "cancelled"
                else:
                    self._current_game.status = "error"

            self.download_finished.emit(self._current_game)

        self._is_downloading = False
        self._current_game = None
        self._downloader = None # Let it be garbage collected
        if self._download_worker_thread and self._download_worker_thread.isRunning():
            self._download_worker_thread.quit()
            self._download_worker_thread.wait()
        self._download_worker_thread = None
        self._selenium_worker = None

        # Start timer for next download
        self._delay_timer.start(self._DOWNLOAD_DELAY_MS)

    def cancel_current_download(self):
        if self._is_downloading and self._current_game:
            print(f"[DownloadQueue] Attempting to cancel download for: {self._current_game.title}")
            if self._selenium_worker:
                self._selenium_worker.request_stop() # This will tell downloader to stop

            # Note: _on_selenium_download_finished will handle the rest of the cleanup
            # and status updates once the download_game method in downloader exits.
            # We might set a flag here if we need to distinguish a manual cancel
            # self._current_game.status = "cancelled" # Or handle in _on_selenium_download_finished
            # self.download_finished.emit(self._current_game) # if we want immediate feedback on cancel

            # Forcing cleanup here might be risky if selenium thread is still running.
            # It's better to let the natural flow of thread completion handle it.
            # The key is that _downloader.stop_download() is called.
            # self._is_downloading = False
            # self._current_game = None
            # self._downloader = None
            # self._delay_timer.start(self._DOWNLOAD_DELAY_MS) # Process next after delay
            # self.queue_changed.emit(len(self._queue))


###############################################################################
# 🧵 Threads for Async Operations                                             #
###############################################################################

class ImageLoadThread(QThread):
    """Поток для асинхронной загрузки изображений."""
    image_loaded = Signal(QPixmap, QLabel) # Pixmap and the target QLabel

    def __init__(self, url: str, target_label: QLabel, target_size: QSize, parent=None):
        super().__init__(parent)
        self.url = url
        self.target_label = target_label
        self.target_size = target_size
        self._base_url_for_images = "https://vimm.net" # Assuming images are relative to this

    def run(self):
        pixmap = QPixmap()
        try:
            full_url = self.url
            if full_url.startswith('//'):
                full_url = 'https:' + full_url
            elif full_url.startswith('/') and not full_url.startswith('//'):
                full_url = self._base_url_for_images + full_url

            if full_url.startswith('data:image'):
                header, data = full_url.split(',', 1)
                image_data = base64.b64decode(data)
                pixmap.loadFromData(image_data)
            else:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': self._base_url_for_images + '/',
                }
                response = requests.get(full_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    pixmap.loadFromData(response.content)

            if not pixmap.isNull():
                pixmap = pixmap.scaled(self.target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_loaded.emit(pixmap, self.target_label)
        except Exception as e:
            print(f"Error loading image {self.url}: {e}")
            self.image_loaded.emit(pixmap, self.target_label) # Emit empty pixmap on error


class GameSearchThread(QThread):
    """Поток для асинхронного поиска игр."""
    results_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, parser: WiiGameParser, query: str, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.query = query

    def run(self):
        try:
            games = self.parser.search_games_online(self.query)
            self.results_ready.emit(games)
        except Exception as e:
            self.error_occurred.emit(str(e))


class GameDetailsThread(QThread):
    """Поток для асинхронной загрузки деталей игры."""
    details_ready = Signal(WiiGame)
    error_occurred = Signal(str)

    def __init__(self, parser: WiiGameParser, game_or_url: WiiGame | str, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.game_or_url = game_or_url

    def run(self):
        try:
            url_to_fetch = ""
            if isinstance(self.game_or_url, WiiGame):
                url_to_fetch = self.game_or_url.detail_url
            else:
                url_to_fetch = self.game_or_url

            if not url_to_fetch:
                self.error_occurred.emit("No detail URL provided for fetching details.")
                return

            detailed_game = self.parser.parse_game_details_from_url(url_to_fetch)
            if detailed_game:
                 # If original game object was passed, merge details
                if isinstance(self.game_or_url, WiiGame) and detailed_game:
                    for attr, value in vars(detailed_game).items():
                        if value: # Only update if new value is not empty
                            setattr(self.game_or_url, attr, value)
                    self.details_ready.emit(self.game_or_url)
                elif detailed_game:
                    self.details_ready.emit(detailed_game)
                else:
                    self.error_occurred.emit(f"Failed to parse details from {url_to_fetch}")
            else:
                self.error_occurred.emit(f"No details found for {url_to_fetch}")
        except Exception as e:
            self.error_occurred.emit(str(e))


###############################################################################
# 🎴 GameCard                                                                #
###############################################################################

class GameCard(QWidget):
    """Отображает подробности об игре и кнопку скачивания."""

    def __init__(self, queue: DownloadQueue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue = queue
        # self.setFixedWidth(560) # Let layout manage size
        self.setObjectName("gameCard") # For styling
        self._game: Optional[WiiGame] = None
        self._image_load_threads: List[ImageLoadThread] = []

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Заголовок ---
        self._title_label = QLabel("Выберите игру слева ✨")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_BLUE};"
            "border-radius:16px;padding:12px;font-size:16pt;font-weight:bold;"
        )
        main_layout.addWidget(self._title_label)

        # --- Изображения ---
        images_container = QWidget()
        images_layout = QHBoxLayout(images_container)
        images_layout.setSpacing(10)

        self._cover_art_label = QLabel("Обложка")
        self._cover_art_label.setFixedSize(200, 280) # Larger cover art
        self._cover_art_label.setAlignment(Qt.AlignCenter)
        self._cover_art_label.setStyleSheet(
            f"background:{WII_LIGHT_GRAY};border:2px dashed {WII_BLUE};border-radius:12px; font-size: 10pt;"
        )
        images_layout.addWidget(self._cover_art_label)

        self._disc_art_label = QLabel("Диск")
        self._disc_art_label.setFixedSize(180, 180) # Larger disc art
        self._disc_art_label.setAlignment(Qt.AlignCenter)
        self._disc_art_label.setStyleSheet(
            f"background:{WII_LIGHT_GRAY};border:2px dashed {WII_BLUE};border-radius:12px; font-size: 10pt;"
        )
        images_layout.addWidget(self._disc_art_label)
        main_layout.addWidget(images_container)

        self._field_labels: Dict[str, QLabel] = {} # To store labels for updating

        # --- General Information Group ---
        general_group = QGroupBox("Основная информация")
        general_group.setStyleSheet(f"QGroupBox {{ font-size: 11pt; font-weight: bold; color: {WII_BLUE}; margin-top: 10px; }}")
        general_layout = QFormLayout(general_group)
        general_layout.setSpacing(6)
        general_layout.setContentsMargins(10, 15, 10, 10) # More top margin for title
        general_layout.setLabelAlignment(Qt.AlignRight)

        info_fields = [
            ("Регион:", "region"), ("Версия:", "version"), ("Языки:", "languages"),
            ("Рейтинг:", "rating"), ("Серийный:", "serial"), ("Игроки:", "players"),
            ("Год:", "year"), ("Размер:", "file_size")
        ]
        for label_text, attr_name in info_fields:
            field_label_widget = QLabel("...")
            field_label_widget.setStyleSheet(f"background-color: {WII_LIGHT_GRAY}; color: {WII_DARK_GRAY}; border: 1px solid {WII_GRAY}; border-radius: 4px; padding: 4px 8px; font-size: 10pt;")
            field_label_widget.setWordWrap(True)
            general_layout.addRow(QLabel(label_text), field_label_widget)
            self._field_labels[attr_name] = field_label_widget
        main_layout.addWidget(general_group)

        # --- Ratings and CRC Group ---
        ratings_group = QGroupBox("Оценки и CRC")
        ratings_group.setStyleSheet(f"QGroupBox {{ font-size: 11pt; font-weight: bold; color: {WII_BLUE}; margin-top: 10px; }}")
        ratings_layout = QFormLayout(ratings_group)
        ratings_layout.setSpacing(6)
        ratings_layout.setContentsMargins(10, 15, 10, 10)
        ratings_layout.setLabelAlignment(Qt.AlignRight)

        rating_fields = [
            ("Графика:", "graphics"), ("Звук:", "sound"), ("Геймплей:", "gameplay"),
            ("Общий:", "overall"), ("CRC:", "crc"), ("Проверено:", "verified")
        ]
        for label_text, attr_name in rating_fields:
            field_label_widget = QLabel("...")
            field_label_widget.setStyleSheet(f"background-color: {WII_LIGHT_GRAY}; color: {WII_DARK_GRAY}; border: 1px solid {WII_GRAY}; border-radius: 4px; padding: 4px 8px; font-size: 10pt;")
            field_label_widget.setWordWrap(True)
            ratings_layout.addRow(QLabel(label_text), field_label_widget)
            self._field_labels[attr_name] = field_label_widget
        main_layout.addWidget(ratings_group)

        # --- Download Buttons and Progress ---
        download_controls_container = QWidget() # Container for buttons and progress
        download_controls_layout = QVBoxLayout(download_controls_container)
        download_controls_layout.setContentsMargins(0,5,0,0) # Add some top margin
        download_controls_layout.setSpacing(8)

        self._download_buttons_layout = QHBoxLayout() # For Download and Cancel buttons

        self._btn_dl = QPushButton("⬇️ Скачать")
        self._btn_dl.setFixedHeight(40)
        self._download_buttons_layout.addWidget(self._btn_dl)

        self._btn_cancel = QPushButton("❌ Отменить")
        self._btn_cancel.setFixedHeight(40)
        self._btn_cancel.setProperty("danger", True)
        self._btn_cancel.hide()
        self._download_buttons_layout.addWidget(self._btn_cancel)
        download_controls_layout.addLayout(self._download_buttons_layout) # Add button layout to container

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(30)
        self._progress_bar.setTextVisible(True) # Show percentage text on bar
        self._progress_bar.hide()
        main_layout.addWidget(self._progress_bar)

        # Labels for download speed and ETA
        self._download_info_layout = QHBoxLayout()
        self._speed_label = QLabel("Скорость: - MB/s")
        self._eta_label = QLabel("ETA: --:--")
        self._download_info_layout.addWidget(self._speed_label)
        self._download_info_layout.addStretch()
        self._download_info_layout.addWidget(self._eta_label)

        self._download_info_widget = QWidget()
        self._download_info_widget.setLayout(self._download_info_layout)
        self._download_info_widget.hide()
        download_controls_layout.addWidget(self._download_info_widget) # Add info to container

        main_layout.addWidget(download_controls_container) # Add container to main card layout
        main_layout.addStretch()

        # --- Подключение сигналов ---
        self._btn_dl.clicked.connect(self._on_download_clicked)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked) # Connect cancel button

        if self.queue:
            self.queue.download_started.connect(self._on_download_started)
            self.queue.download_finished.connect(self._on_download_finished)
            self.queue.progress_changed.connect(self._on_progress_changed)

        self._clear_card()

    def _clear_card(self):
        self._title_label.setText("Выберите игру")
        self._cover_art_label.setText("Обложка")
        self._cover_art_label.setPixmap(QPixmap()) # Clear image
        self._disc_art_label.setText("Диск")
        self._disc_art_label.setPixmap(QPixmap())
        for label in self._field_labels.values():
            label.setText("...")

        self._btn_dl.show()
        self._btn_dl.setText("⬇️ Скачать")
        self._btn_dl.setEnabled(False)
        self._btn_cancel.hide()
        self._progress_bar.hide()
        self._progress_bar.setValue(0)
        self._download_info_widget.hide()
        self._speed_label.setText("Скорость: - MB/s")
        self._eta_label.setText("ETA: --:--")
        self._game = None

    def _on_download_clicked(self):
        if self._game and self.queue:
            self.queue.add(self._game)
            self._update_download_button_state()

    @Slot()
    def _on_cancel_clicked(self):
        if self._game and self.queue:
            print(f"[GameCard] Cancel clicked for {self._game.title}")
            self.queue.cancel_current_download()
            # The queue will emit signals that will eventually call _update_download_button_state

    @Slot(WiiGame)
    def _on_download_started(self, game: WiiGame):
        if self._game and game.title == self._game.title:
            self._progress_bar.setValue(0) # Reset progress for new download start
            self._update_download_button_state()

    @Slot(WiiGame)
    def _on_download_finished(self, game: WiiGame): # game here is the one from the signal
        # Check if the finished game is the one currently displayed on the card
        if self._game and game.title == self._game.title:
            self._update_download_button_state() # This will hide progress bar if status is not "downloading"
            if getattr(self._game, "status", "new") != "downloading":
                 self._download_info_widget.hide()


    @Slot(WiiGame, int, float, float, float, str) # game, percent, downloaded_bytes, total_bytes, speed_mbps, eta_str
    def _on_progress_changed(self, game: WiiGame, percent: int, downloaded_bytes: float, total_bytes: float, speed_mbps: float, eta_str: str):
        if self._game and game.title == self._game.title:
            self._progress_bar.setValue(percent)
            self._speed_label.setText(f"Скорость: {speed_mbps:.2f} MB/s")
            self._eta_label.setText(f"ETA: {eta_str}")

            # Ensure progress bar and info are visible if download is ongoing for this game
            current_status = getattr(self._game, "status", "new")
            if current_status == "downloading":
                if not self._progress_bar.isVisible(): self._progress_bar.show()
                if not self._download_info_widget.isVisible(): self._download_info_widget.show()
            else: # If status changed (e.g. cancelled, error) while progress signal came
                self._progress_bar.hide()
                self._download_info_widget.hide()


    def _update_download_button_state(self):
        if not self._game:
            self._btn_dl.show()
            self._btn_dl.setEnabled(False)
            self._btn_dl.setText("⬇️ Скачать")
            self._btn_cancel.hide()
            self._progress_bar.hide()
            return

        status = getattr(self._game, "status", "new")

        if status == "downloading":
            self._btn_dl.hide()
            self._btn_cancel.show()
            self._progress_bar.show()
        elif status == "queued":
            self._btn_dl.show()
            self._btn_dl.setText("⌛ В очереди")
            self._btn_dl.setEnabled(False)
            self._btn_cancel.hide()
            self._progress_bar.hide()
        elif status == "downloaded":
            self._btn_dl.show()
            self._btn_dl.setText("✅ Скачано")
            self._btn_dl.setEnabled(False)
            self._btn_cancel.hide()
            self._progress_bar.hide()
        elif status == "error":
            self._btn_dl.show()
            self._btn_dl.setText("⚠️ Ошибка")
            self._btn_dl.setEnabled(False) # Or True to retry, TBD
            self._btn_cancel.hide()
            self._progress_bar.hide()
        else: # "new" or "cancelled" or any other
            self._btn_dl.show()
            self._btn_dl.setText("⬇️ Скачать")
            self._btn_dl.setEnabled(bool(self._game.detail_url) and bool(self._game.download_url or self._game.detail_url)) # Enable if URL exists
            self._btn_cancel.hide()
            self._progress_bar.hide()

    def update_game(self, game: Optional[WiiGame]):
        if not game:
            self._clear_card()
            return

        self._game = game
        self._title_label.setText(game.title or "Без названия")

        # Update text fields
        for attr_name, label_widget in self._field_labels.items():
            value = getattr(game, attr_name, None)
            label_widget.setText(str(value) if value else "...")
            if len(str(value)) > 30 : # Prevent very long text
                 label_widget.setToolTip(str(value)) # Show full text on hover
                 label_widget.setText(str(value)[:27] + "...")


        # Clear previous images and stop old threads
        self._cover_art_label.setText("Загрузка обложки...")
        self._cover_art_label.setPixmap(QPixmap())
        self._disc_art_label.setText("Загрузка диска...")
        self._disc_art_label.setPixmap(QPixmap())

        for thread in self._image_load_threads:
            if thread.isRunning():
                thread.quit() # Request thread termination
                thread.wait() # Wait for it to finish
        self._image_load_threads.clear()


        if game.box_art:
            box_thread = ImageLoadThread(game.box_art, self._cover_art_label, self._cover_art_label.size(), self)
            box_thread.image_loaded.connect(self._on_image_loaded)
            box_thread.start()
            self._image_load_threads.append(box_thread)
        else:
            self._cover_art_label.setText("Нет обложки")

        if game.disc_art:
            disc_thread = ImageLoadThread(game.disc_art, self._disc_art_label, self._disc_art_label.size(), self)
            disc_thread.image_loaded.connect(self._on_image_loaded)
            disc_thread.start()
            self._image_load_threads.append(disc_thread)
        else:
            self._disc_art_label.setText("Нет диска")

        self._update_download_button_state()

    @Slot(QPixmap, QLabel)
    def _on_image_loaded(self, pixmap: QPixmap, target_label: QLabel):
        if not pixmap.isNull():
            target_label.setPixmap(pixmap)
        else:
            if target_label == self._cover_art_label:
                target_label.setText("Обложка не найдена")
            elif target_label == self._disc_art_label:
                target_label.setText("Диск не найден")


###############################################################################
# 🌟 Animated navigation button                                               #
###############################################################################

class AnimatedNavButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setProperty("nav", True)
        self.setCheckable(True)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def enterEvent(self, e):  # noqa: N802
        if not self.isChecked():
            self._scale(1.05)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        if not self.isChecked():
            self._scale(1.0)
        super().leaveEvent(e)

    def _scale(self, k: float):
        r = self.geometry()
        c = r.center()
        self._anim.stop()
        self._anim.setStartValue(r)
        self._anim.setEndValue(QRectF(c.x()-r.width()*k/2, c.y()-r.height()*k/2, r.width()*k, r.height()*k).toRect())
        self._anim.start()

###############################################################################
# 🖥️ Main window                                                             #
###############################################################################

class WiiUnifiedManager(QMainWindow):
    """Главное окно приложения."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("🎮 Wii Unified Manager 2.5") # Version bump
        self.resize(1350, 900) # Slightly larger window
        self.setWindowIcon(QIcon()) # TODO: Add an actual icon
        self.setStyleSheet(build_style())

        # Services
        self.parser = WiiGameParser()
        self.db = WiiGameDatabase() # Initialize database
        self.queue = DownloadQueue(self)
        # self.downloader = WiiGameSeleniumDownloader() # For later

        # UI layout
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QLabel("🎮 Wii Unified Manager")
        header.setProperty("headerTitle", True)
        header.setAlignment(Qt.AlignCenter)
        root.addWidget(header)

        nav = QHBoxLayout()
        self.btn_search = AnimatedNavButton("🔍 Поиск")
        self.btn_manager = AnimatedNavButton("💾 Менеджер")
        self.btn_search.setChecked(True)
        nav.addStretch()
        nav.addWidget(self.btn_search)
        nav.addWidget(self.btn_manager)
        nav.addStretch()
        root.addLayout(nav)

        self.stack = QStackedWidget()
        self.page_search = self._build_search_page()
        self.page_manager = self._build_manager_page()
        self.stack.addWidget(self.page_search)
        self.stack.addWidget(self.page_manager)
        root.addWidget(self.stack)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Готов к работе 🔋")
        self._setup_menu_actions() # Setup menu bar

        self._games: List[WiiGame] = [] # Holds current list of games (search results or cache)
        self.current_usb_drive: Optional[Drive] = None
        self.download_dir = Path("downloads") # Define download directory
        self.download_dir.mkdir(exist_ok=True) # Ensure it exists

        # Progress bar for manager operations (like copy to USB)
        self.manager_progress_bar = QProgressBar()
        self.manager_progress_bar.setFixedHeight(25)
        self.manager_progress_bar.setTextVisible(True)
        self.manager_progress_bar.hide()
        # Add it to the status bar or a dedicated panel later if complex layout needed
        # For now, it will be shown/hidden dynamically by operations.

        self._connect_signals()
        self._load_cached_games() # Load games from DB on startup
        if ENHANCED_DRIVE_AVAILABLE:
            self._refresh_drives_list() # Populate drive list on startup

    # ------------------------------------------------------------------
    def _setup_menu_actions(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&Файл")

        export_action = QAction("Экспорт в JSON...", self)
        export_action.triggered.connect(self._action_export_to_json)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools Menu
        tools_menu = menubar.addMenu("&Инструменты")

        clear_cache_action = QAction("Очистить кеш игр...", self)
        clear_cache_action.triggered.connect(self._action_clear_cache)
        tools_menu.addAction(clear_cache_action)

        # Help Menu
        help_menu = menubar.addMenu("&Справка")
        about_action = QAction("О программе...", self)
        about_action.triggered.connect(self._action_show_about)
        help_menu.addAction(about_action)

    def _action_export_to_json(self):
        games_to_export = self.db.games # Access games directly from the database
        if not games_to_export:
            QMessageBox.information(self, "Экспорт", "Нет игр в базе для экспорта.")
            return

        default_filename = f"wii_games_export_{time.strftime('%Y%m%d')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт игр в JSON", default_filename, "JSON файлы (*.json)"
        )

        if file_path:
            try:
                data_to_save = [game.to_dict() for game in games_to_export]
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "Экспорт успешен", f"Данные игр сохранены в:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка экспорта", f"Не удалось сохранить файл: {e}")

    def _action_clear_cache(self):
        reply = QMessageBox.question(self, "Очистка кеша",
                                     "Вы уверены, что хотите очистить весь кеш игр?\n"
                                     "Это удалит все сохраненные данные о найденных играх.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.games.clear() # Assuming direct access or provide a clear method in DB
            self.db.save_database() # Save the empty list
            self._games = []
            self.list_results.clear()
            self.card.update_game(None) # Clear the game card
            # Also clear manager lists if they show cached data indirectly
            self._refresh_downloaded_games_list()
            if ENHANCED_DRIVE_AVAILABLE:
                self._refresh_usb_games_list()
            self.status.showMessage("Кеш игр очищен.")
            QMessageBox.information(self, "Кеш очищен", "Локальный кеш информации об играх был успешно очищен.")

    def _action_show_about(self):
        QMessageBox.about(self, "О Wii Unified Manager",
                          "<h3>🎮 Wii Unified Manager</h3>"
                          "<p>Версия 2.5 (сборка Jules)</p>"
                          "<p>Менеджер для поиска, загрузки и управления играми Nintendo Wii.</p>"
                          "<p><b>Возможности:</b></p>"
                          "<ul>"
                          "<li>Онлайн поиск игр (vimm.net)</li>"
                          "<li>Асинхронная загрузка деталей и изображений</li>"
                          "<li>Очередь загрузок с использованием Selenium</li>"
                          "<li>Управление локальными файлами игр</li>"
                          "<li>Управление играми на USB (если доступно)</li>"
                          "<li>Экспорт списка игр в JSON</li>"
                          "<li>Приятный интерфейс в стиле Wii</li>"
                          "</ul>"
                          "<p>Разработано с использованием PySide6.</p>"
                          "<p>© Jules AI Assistant & User</p>")


    # ------------------------------------------------------------------
    def _build_search_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {WII_LIGHT_GRAY};") # Ensure page background
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(5,5,5,5) # Add some margin

        # --- Search Input Area ---
        search_input_container = QWidget()
        search_input_layout = QHBoxLayout(search_input_container)
        search_input_layout.setContentsMargins(0,0,0,0)
        self.edit_query = QLineEdit()
        self.edit_query.setPlaceholderText("Введите название игры для поиска (например, Mario) или оставьте пустым для загрузки всех из кеша")
        self.edit_query.setFixedHeight(40)
        self.btn_go_search = QPushButton("🔍 Найти") # Renamed to be specific
        self.btn_go_search.setFixedHeight(40)
        search_input_layout.addWidget(self.edit_query, 1) # Give more stretch to input
        search_input_layout.addWidget(self.btn_go_search)
        vbox.addWidget(search_input_container)

        # --- Main Content Splitter ---
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel: Game List
        self.list_results = QListWidget()
        self.list_results.setObjectName("gameListWidget") # For styling if needed
        self.list_results.setFixedWidth(450) # Give a bit more space for game list

        # Right Panel: Game Card (inside a ScrollArea for long content)
        self.card_scroll_area = QScrollArea()
        self.card_scroll_area.setWidgetResizable(True)
        self.card_scroll_area.setObjectName("gameCardScrollArea")
        self.card_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # Important for aesthetics

        self.card = GameCard(self.queue, parent=self.card_scroll_area) # Pass queue
        self.card_scroll_area.setWidget(self.card)

        splitter.addWidget(self.list_results)
        splitter.addWidget(self.card_scroll_area) # Add scroll area instead of card directly
        splitter.setStretchFactor(0,1) # list_results
        splitter.setStretchFactor(1,2) # card_scroll_area (give more space to card)
        splitter.setSizes([450, 900]) # Initial sizes, can be adjusted by user

        vbox.addWidget(splitter)
        return page

    # ------------------------------------------------------------------
    def _build_manager_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {WII_LIGHT_GRAY};") # Ensure page background
        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(5,5,5,5)

        # --- Top controls for USB (if available) ---
        if ENHANCED_DRIVE_AVAILABLE:
            usb_controls_widget = QWidget()
            usb_controls_layout = QHBoxLayout(usb_controls_widget)
            usb_controls_layout.setContentsMargins(0,0,0,5) # Bottom margin

            drive_label = QLabel("USB Диск:")
            self.drive_combo = QComboBox()
            self.drive_combo.setPlaceholderText("Выберите USB диск")
            self.drive_combo.setMinimumWidth(200)
            self.drive_combo.setFixedHeight(35)

            self.btn_refresh_drives = QPushButton("🔄")
            self.btn_refresh_drives.setFixedSize(35, 35)
            self.btn_refresh_drives.setToolTip("Обновить список дисков")
            # btn_refresh_drives could also have a neutral or info style if desired

            self.btn_import_external = QPushButton("📁 Импорт игр на USB")
            self.btn_import_external.setFixedHeight(35)
            self.btn_import_external.setProperty("success", True) # Make it green
            self.btn_import_external.setEnabled(False) # Enable when drive selected

            usb_controls_layout.addWidget(drive_label)
            usb_controls_layout.addWidget(self.drive_combo, 1)
            usb_controls_layout.addWidget(self.btn_refresh_drives)
            usb_controls_layout.addStretch()
            usb_controls_layout.addWidget(self.btn_import_external)
            root_layout.addWidget(usb_controls_widget)
        else:
            no_usb_label = QLabel("Функции USB не доступны (модуль EnhancedDrive не найден).")
            no_usb_label.setAlignment(Qt.AlignCenter)
            no_usb_label.setStyleSheet("padding: 10px; background-color: #fff0f0; color: #d00; border-radius: 8px;")
            root_layout.addWidget(no_usb_label)

        # --- Main Content Splitter ---
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel: Tabbed lists for Local and USB games
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0,0,0,0)

        self.manager_tabs = QTabWidget()
        self.manager_tabs.setObjectName("managerTabs")

        # Tab 1: Local Downloaded Games
        local_tab = QWidget()
        local_tab_layout = QVBoxLayout(local_tab)
        local_tab_layout.setContentsMargins(2,2,2,2)
        self.list_downloaded_games = QListWidget()
        self.list_downloaded_games.setObjectName("downloadedGamesList")
        local_tab_layout.addWidget(self.list_downloaded_games)
        self.manager_tabs.addTab(local_tab, "📥 Локальные")

        # Tab 2: USB/Flash Games
        usb_tab = QWidget()
        usb_tab_layout = QVBoxLayout(usb_tab)
        usb_tab_layout.setContentsMargins(2,2,2,2)
        self.list_usb_games = QListWidget()
        self.list_usb_games.setObjectName("usbGamesList")
        if not ENHANCED_DRIVE_AVAILABLE:
            self.list_usb_games.setEnabled(False) # Disable if no drive module
        usb_tab_layout.addWidget(self.list_usb_games)
        self.manager_tabs.addTab(usb_tab, "💾 USB/Flash")

        left_panel_layout.addWidget(self.manager_tabs)
        left_panel_widget.setMinimumWidth(450) # Ensure left panel is wide enough
        splitter.addWidget(left_panel_widget)

        # Right Panel: Manager Game Card (placeholder for now)
        self.manager_card_scroll_area = QScrollArea()
        self.manager_card_scroll_area.setWidgetResizable(True)
        self.manager_card_scroll_area.setObjectName("managerCardScrollArea")
        self.manager_card_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # TODO: Create a dedicated ManagerGameCard widget
        self.manager_card_placeholder = QLabel("Выберите игру из списка для управления.")
        self.manager_card_placeholder.setAlignment(Qt.AlignCenter)
        self.manager_card_placeholder.setStyleSheet(
            f"background:{WII_LIGHT_GRAY};border:2px dashed {WII_GRAY};"
            "border-radius:16px;padding:20px;font-size:14pt;"
        )
        self.manager_card_scroll_area.setWidget(self.manager_card_placeholder) # Placeholder for now

        # Create actual ManagerGameCard instance here
        self.manager_card = ManagerGameCard(self) # Pass main window as parent for potential actions
        self.manager_card_scroll_area.setWidget(self.manager_card)


        splitter.addWidget(self.manager_card_scroll_area)
        splitter.setStretchFactor(0,1)
        splitter.setStretchFactor(1,2)
        splitter.setSizes([450, 900])

        root_layout.addWidget(splitter)
        return page

    # ------------------------------------------------------------------
    def _refresh_drives_list(self):
        if not ENHANCED_DRIVE_AVAILABLE: return
        self.drive_combo.clear()
        try:
            drives = Drive.get_drives()
            if not drives:
                self.drive_combo.addItem("Нет USB дисков")
                self.drive_combo.setEnabled(False)
                return

            self.drive_combo.setEnabled(True)
            self.drive_combo.addItem("Выберите диск...", None) # Placeholder
            for drive in drives:
                self.drive_combo.addItem(f"{drive.name} ({drive.available_space}GB свободно)", drive)
        except Exception as e:
            print(f"Error refreshing drives: {e}")
            self.drive_combo.addItem("Ошибка загрузки дисков")
            self.drive_combo.setEnabled(False)

    def _on_drive_selected(self, index: int):
        if not ENHANCED_DRIVE_AVAILABLE or index <= 0: # index 0 is placeholder
            self.current_usb_drive = None
            self.list_usb_games.clear()
            self.manager_card.clear_card() # Clear manager card
            self.btn_import_external.setEnabled(False)
            return

        self.current_usb_drive = self.drive_combo.itemData(index)
        if self.current_usb_drive:
            self.btn_import_external.setEnabled(True)
            self._refresh_usb_games_list()
        else:
            self.btn_import_external.setEnabled(False)


    def _refresh_downloaded_games_list(self):
        self.list_downloaded_games.clear()
        self.manager_card.clear_card() # Clear card when list refreshes
        try:
            # Common game file extensions
            game_extensions = ["*.wbfs", "*.iso", "*.rvz", "*.wad"]
            downloaded_files = []
            for ext in game_extensions:
                downloaded_files.extend(self.download_dir.glob(ext))

            if not downloaded_files:
                item = QListWidgetItem("Нет скачанных игр")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable) # Non-selectable
                self.list_downloaded_games.addItem(item)
                return

            for file_path in sorted(downloaded_files, key=lambda p: p.name):
                size_gb = file_path.stat().st_size / (1024**3)
                item = QListWidgetItem(f"{file_path.name}\n ({size_gb:.2f} GB)")
                item.setData(Qt.UserRole, file_path) # Store Path object
                self.list_downloaded_games.addItem(item)
        except Exception as e:
            print(f"Error refreshing downloaded games list: {e}")
            self.list_downloaded_games.addItem("Ошибка загрузки списка")

    def _refresh_usb_games_list(self):
        self.list_usb_games.clear()
        self.manager_card.clear_card()
        if not ENHANCED_DRIVE_AVAILABLE or not self.current_usb_drive:
            item = QListWidgetItem("USB диск не выбран")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.list_usb_games.addItem(item)
            return

        try:
            usb_games = self.current_usb_drive.get_games() # Returns List[FlashGame]
            if not usb_games:
                item = QListWidgetItem("Нет игр на USB диске")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.list_usb_games.addItem(item)
                return

            for game in sorted(usb_games, key=lambda g: g.display_title):
                size_gb = game.size / (1024**3)
                item = QListWidgetItem(f"{game.display_title}\n ({size_gb:.2f} GB)")
                item.setData(Qt.UserRole, game) # Store FlashGame object
                self.list_usb_games.addItem(item)
        except Exception as e:
            print(f"Error refreshing USB games list: {e}")
            self.list_usb_games.addItem("Ошибка загрузки списка игр с USB")
            QMessageBox.warning(self, "Ошибка USB", f"Не удалось прочитать игры с диска {self.current_usb_drive.name}: {e}")


    def _on_local_game_selected_manager(self, current_item: Optional[QListWidgetItem], previous_item: Optional[QListWidgetItem]):
        if current_item:
            file_path = current_item.data(Qt.UserRole)
            if isinstance(file_path, Path):
                self.manager_card.update_for_local_file(file_path, self.current_usb_drive is not None)
        else:
            self.manager_card.clear_card()

    def _on_usb_game_selected_manager(self, current_item: Optional[QListWidgetItem], previous_item: Optional[QListWidgetItem]):
        if current_item:
            flash_game = current_item.data(Qt.UserRole)
            if ENHANCED_DRIVE_AVAILABLE and isinstance(flash_game, FlashGame): # Check type
                self.manager_card.update_for_usb_game(flash_game)
        else:
            self.manager_card.clear_card()

    def _on_manager_tab_changed(self, index: int):
        """Called when the user switches tabs in the Manager section."""
        self.manager_card.clear_card() # Clear card details
        if index == 0: # Local files tab
            self._refresh_downloaded_games_list()
            if self.list_downloaded_games.count() > 0 and self.list_downloaded_games.item(0).flags() & Qt.ItemIsSelectable:
                self.list_downloaded_games.setCurrentRow(0)
        elif index == 1: # USB games tab
            if ENHANCED_DRIVE_AVAILABLE and self.current_usb_drive:
                self._refresh_usb_games_list()
                if self.list_usb_games.count() > 0 and self.list_usb_games.item(0).flags() & Qt.ItemIsSelectable:
                    self.list_usb_games.setCurrentRow(0)
            elif ENHANCED_DRIVE_AVAILABLE and not self.current_usb_drive:
                 self.list_usb_games.clear()
                 item = QListWidgetItem("USB диск не выбран для отображения игр.")
                 item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                 self.list_usb_games.addItem(item)


    # --- Action Implementations for ManagerGameCard ---
    def _action_install_to_usb(self, local_file_path: Optional[Path]):
        if not local_file_path:
            QMessageBox.warning(self, "Установка на USB", "Файл для установки не определен.")
            return
        if not self.current_usb_drive:
            QMessageBox.warning(self, "Установка на USB", "USB диск не выбран.")
            return

        reply = QMessageBox.question(self, "Подтверждение установки",
                                     f"Установить игру '{local_file_path.name}' на USB диск '{self.current_usb_drive.name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._start_copy_to_usb([local_file_path])

    def _action_delete_local_file(self, local_file_path: Optional[Path]):
        if not local_file_path:
            QMessageBox.warning(self, "Удаление файла", "Файл для удаления не определен.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления",
                                     f"Вы действительно хотите удалить локальный файл:\n{local_file_path}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                local_file_path.unlink()
                QMessageBox.information(self, "Удаление успешно", f"Файл '{local_file_path.name}' удален.")
                self._refresh_downloaded_games_list()
                self.manager_card.clear_card()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка удаления", f"Не удалось удалить файл: {e}")

    def _action_delete_from_usb(self, flash_game: Optional[FlashGame]):
        if not flash_game:
            QMessageBox.warning(self, "Удаление с USB", "Игра для удаления с USB не определена.")
            return
        if not self.current_usb_drive: # Should not happen if button is enabled
            QMessageBox.warning(self, "Удаление с USB", "USB диск не выбран.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления с USB",
                                     f"Вы действительно хотите удалить игру '{flash_game.display_title}'\nс USB диска '{self.current_usb_drive.name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if hasattr(flash_game, 'delete') and callable(flash_game.delete):
                    flash_game.delete() # Assuming FlashGame has a delete method
                    QMessageBox.information(self, "Удаление успешно", f"Игра '{flash_game.display_title}' удалена с USB.")
                    self._refresh_usb_games_list()
                    self.manager_card.clear_card()
                else:
                    raise NotImplementedError("Метод delete() отсутствует у объекта игры на флешке.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка удаления с USB", f"Не удалось удалить игру с USB: {e}")

    def _action_import_external_to_usb(self):
        if not self.current_usb_drive:
            QMessageBox.warning(self, "Импорт на USB", "USB диск не выбран для импорта.")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Выберите файлы игр для импорта на USB", "",
            "Файлы игр (*.wbfs *.iso *.rvz *.wad);;Все файлы (*)"
        )
        if file_paths:
            paths_to_copy = [Path(fp) for fp in file_paths]
            self._start_copy_to_usb(paths_to_copy)


    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.btn_search.clicked.connect(lambda: self._switch_page(self.page_search, self.btn_search))
        self.btn_manager.clicked.connect(lambda: self._switch_page(self.page_manager, self.btn_manager))

        # Search Page Signals
        self.btn_go_search.clicked.connect(self._trigger_search_or_load_cache)
        self.edit_query.returnPressed.connect(self._trigger_search_or_load_cache)
        self.list_results.currentItemChanged.connect(self._on_game_selected_from_list)

        # Manager Page Signals
        if ENHANCED_DRIVE_AVAILABLE:
            self.drive_combo.currentIndexChanged.connect(self._on_drive_selected)
            self.btn_refresh_drives.clicked.connect(self._refresh_drives_list)
            self.btn_import_external.clicked.connect(self._action_import_external_to_usb)

        self.list_downloaded_games.currentItemChanged.connect(self._on_local_game_selected_manager)
        self.list_usb_games.currentItemChanged.connect(self._on_usb_game_selected_manager)
        if hasattr(self, 'manager_tabs'): # manager_tabs might not exist if ENHANCED_DRIVE_AVAILABLE is false and layout changes
            self.manager_tabs.currentChanged.connect(self._on_manager_tab_changed)


        # DownloadQueue Signals
        self.queue.queue_changed.connect(self._update_status_bar_queue_info)
        self.queue.download_started.connect(self._on_actual_download_started)
        self.queue.download_finished.connect(self._on_actual_download_finished)
        self.queue.progress_changed.connect(self._on_actual_download_progress)


    def _update_status_bar_queue_info(self, count: int):
        self.status.showMessage(f"Очередь: {count} игр")

    def _on_actual_download_started(self, game: WiiGame):
        self.status.showMessage(f"⬇️ Скачивание: {game.title}…")
        self.card.update_game(game) # Refresh card to show progress
        self._update_list_item_for_game(game)


    def _on_actual_download_finished(self, game: WiiGame):
        self.status.showMessage(f"✅ Завершено: {game.title}")
        self.card.update_game(game) # Refresh card
        self._update_list_item_for_game(game)
        QMessageBox.information(self, "Загрузка завершена", f"Игра '{game.title}' скачана.")


    def _on_actual_download_progress(self, game: WiiGame, percent: int, downloaded_bytes: float, total_bytes: float, speed_mbps: float, eta_str: str):
        # Status bar could show overall progress if multiple downloads were allowed
        # For now, card handles its own progress if it's the selected game
        if self.card._game and self.card._game.title == game.title:
            self.card._on_progress_changed(game, percent, downloaded_bytes, total_bytes, speed_mbps, eta_str)
        # We could also update a progress bar in the list item itself if desired

    # ------------------------------------------------------------------
    def _switch_page(self, page: QWidget, btn: QPushButton):
        self.btn_search.setChecked(page == self.page_search)
        self.btn_manager.setChecked(page == self.page_manager)
        # Animate buttons
        self.btn_search._scale(1.05 if page == self.page_search else 1.0)
        self.btn_manager._scale(1.05 if page == self.page_manager else 1.0)
        self.stack.setCurrentWidget(page)
        self.status.showMessage(f"Раздел: {btn.text().strip().replace('🔍','').replace('💾','').strip()}")

    # ------------------------------------------------------------------
    def _load_cached_games(self):
        """Загружает игры из локальной базы данных (JSON файла)."""
        self.status.showMessage("Загрузка игр из кеша...")
        self.db.load_database() # WiiGameDatabase handles the loading
        cached_games = self.db.games # Access games directly from the database
        self._populate_game_list(cached_games)
        if cached_games:
            self.status.showMessage(f"Загружено {len(cached_games)} игр из кеша.")
            self.list_results.setCurrentRow(0) # Select first game
        else:
            self.status.showMessage("Кеш игр пуст. Попробуйте выполнить поиск.")
            self.card.update_game(None) # Clear card if no games

    # ------------------------------------------------------------------
    def _trigger_search_or_load_cache(self):
        query = self.edit_query.text().strip()
        if not query:
            # If query is empty, load all games from cache
            self._load_cached_games()
        else:
            self._perform_online_search(query)

    # ------------------------------------------------------------------
    def _perform_online_search(self, query: str):
        self.status.showMessage(f"Поиск «{query}» онлайн…")
        self.list_results.clear() # Clear previous results
        self.card.update_game(None) # Clear card
        self.btn_go_search.setEnabled(False)
        self.edit_query.setEnabled(False)

        self.search_thread = GameSearchThread(self.parser, query, self)
        self.search_thread.results_ready.connect(self._on_search_results_ready)
        self.search_thread.error_occurred.connect(self._on_search_error)
        self.search_thread.finished.connect(self._on_search_finished) # Re-enable buttons
        self.search_thread.start()

    @Slot(list)
    def _on_search_results_ready(self, games: List[WiiGame]):
        self.db.add_games(games) # Add/update in local DB
        self.db.save_database()
        self._populate_game_list(games)
        if games:
            self.status.showMessage(f"Найдено {len(games)} игр для «{self.edit_query.text().strip()}».")
            self.list_results.setCurrentRow(0)
        else:
            self.status.showMessage(f"Игры не найдены для «{self.edit_query.text().strip()}».")
            self.card.update_game(None)

    @Slot(str)
    def _on_search_error(self, error_message: str):
        self.status.showMessage(f"Ошибка поиска: {error_message}")
        QMessageBox.warning(self, "Ошибка поиска", f"Не удалось выполнить поиск: {error_message}")

    def _on_search_finished(self):
        self.btn_go_search.setEnabled(True)
        self.edit_query.setEnabled(True)

    # ------------------------------------------------------------------
    def _populate_game_list(self, games: List[WiiGame]):
        self._games = sorted(games, key=lambda g: g.title) # Sort games by title
        self.list_results.clear()
        for game in self._games:
            item = QListWidgetItem()
            self._update_list_item_display(item, game) # Use helper to set text and icon
            item.setData(Qt.UserRole, game) # Store the WiiGame object
            self.list_results.addItem(item)

        if self._games:
            self.list_results.setCurrentRow(0) # Select first item if list is not empty
        else:
            self.card.update_game(None) # Clear card if no games

    def _update_list_item_display(self, item: QListWidgetItem, game: WiiGame):
        """Updates the text and icon of a list widget item based on game status."""
        status_icon = "🎮" # Default
        if getattr(game, 'status', 'new') == 'downloaded':
            status_icon = "✅"
        elif getattr(game, 'status', 'new') == 'downloading':
            status_icon = "⬇️"
        elif getattr(game, 'status', 'new') == 'queued':
            status_icon = "⌛"
        # Add more statuses like 'on_flash' later:
        # elif self.is_game_on_flash(game): # This function would need to be implemented
        #     status_icon = "💾"

        item_text = f"{status_icon} {game.title}\n"
        details = []
        if game.region: details.append(f"🌍 {game.region}")
        if game.rating: details.append(f"⭐ {game.rating}")
        item_text += " • ".join(details)
        item.setText(item_text)

    def _update_list_item_for_game(self, game_to_update: WiiGame):
        """Finds and updates a specific game's display in the list_results."""
        for i in range(self.list_results.count()):
            item = self.list_results.item(i)
            game_in_list = item.data(Qt.UserRole)
            if game_in_list and game_in_list.title == game_to_update.title: # Simple check by title
                self._update_list_item_display(item, game_to_update)
                break
    # ------------------------------------------------------------------
    @Slot(QListWidgetItem, QListWidgetItem) # current, previous
    def _on_game_selected_from_list(self, current_item: Optional[QListWidgetItem], previous_item: Optional[QListWidgetItem]):
        if not current_item:
            self.card.update_game(None) # Clear card if no selection
            return

        game = current_item.data(Qt.UserRole)
        if isinstance(game, WiiGame):
            self.card.update_game(game) # Update the card with the basic game object first

            # If detailed information is missing, fetch it
            if not game.serial and game.detail_url: # 'serial' is a good indicator of detailed info
                self.status.showMessage(f"Загрузка деталей для {game.title}...")
                self.details_thread = GameDetailsThread(self.parser, game, self) # Pass the game object
                self.details_thread.details_ready.connect(self._on_game_details_ready)
                self.details_thread.error_occurred.connect(self._on_game_details_error)
                self.details_thread.start()

    @Slot(WiiGame)
    def _on_game_details_ready(self, detailed_game: WiiGame):
        self.status.showMessage(f"Детали для {detailed_game.title} загружены.")
        self.db.add_games([detailed_game]) # Update DB with detailed info
        self.db.save_database()

        # Update the card if the currently selected game is the one whose details were loaded
        current_selected_item = self.list_results.currentItem()
        if current_selected_item:
            selected_game_in_list = current_selected_item.data(Qt.UserRole)
            if selected_game_in_list and selected_game_in_list.title == detailed_game.title:
                 # Crucially, update the game object in the list_results' UserRole as well
                current_selected_item.setData(Qt.UserRole, detailed_game)
                self.card.update_game(detailed_game)

        # Also, update the game in our main self._games list
        for i, g in enumerate(self._games):
            if g.title == detailed_game.title: # Or better, by a unique ID if available
                self._games[i] = detailed_game
                break


    @Slot(str)
    def _on_game_details_error(self, error_message: str):
        self.status.showMessage(f"Ошибка загрузки деталей: {error_message}")
        # Optionally show a QMessageBox to the user
        # QMessageBox.warning(self, "Ошибка деталей", f"Не удалось загрузить детали: {error_message}")

###############################################################################
# 🃏 ManagerGameCard - Displays info for local or USB games in Manager section #
###############################################################################
class ManagerGameCard(QWidget):
    def __init__(self, main_window: 'WiiUnifiedManager', parent: Optional[QWidget] = None): # Forward reference
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("managerGameCard")
        self.current_local_file_path: Optional[Path] = None
        self.current_flash_game: Optional[FlashGame] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15,15,15,15)

        self.title_label = QLabel("Информация об элементе")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_GREEN};" # Green border for manager card
            "border-radius:12px;padding:10px;font-size:14pt;font-weight:bold;"
        )
        layout.addWidget(self.title_label)

        self.info_widget = QWidget()
        self.info_layout = QFormLayout(self.info_widget)
        self.info_layout.setSpacing(8)
        self.info_layout.setContentsMargins(5,5,5,5)
        self.info_layout.setLabelAlignment(Qt.AlignRight) # Align labels to the right
        layout.addWidget(self.info_widget)

        # Action Buttons
        self.btn_install_to_usb = QPushButton("💾 Установить на USB")
        self.btn_install_to_usb.setProperty("success", True)
        self.btn_delete_local = QPushButton("🗑️ Удалить файл")
        self.btn_delete_local.setProperty("danger", True)
        self.btn_delete_from_usb = QPushButton("❌ Удалить с USB")
        self.btn_delete_from_usb.setProperty("danger", True)

        self.buttons: List[QPushButton] = [self.btn_install_to_usb, self.btn_delete_local, self.btn_delete_from_usb]

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_install_to_usb)
        buttons_layout.addWidget(self.btn_delete_local)
        buttons_layout.addWidget(self.btn_delete_from_usb)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        layout.addStretch() # Push content to top

        # Connect buttons
        self.btn_install_to_usb.clicked.connect(lambda: self.main_window._action_install_to_usb(self.current_local_file_path) if self.current_local_file_path else None)
        self.btn_delete_local.clicked.connect(lambda: self.main_window._action_delete_local_file(self.current_local_file_path) if self.current_local_file_path else None)
        self.btn_delete_from_usb.clicked.connect(lambda: self.main_window._action_delete_from_usb(self.current_flash_game) if self.current_flash_game else None)

        self.clear_card() # Initial state

    def clear_card_content(self):
        """Clears the content of the info_layout."""
        while self.info_layout.rowCount() > 0:
            self.info_layout.removeRow(0)
        self.current_local_file_path = None
        self.current_flash_game = None

    def clear_card(self):
        self.clear_card_content()
        self.title_label.setText("Выберите элемент из списка")
        self.set_buttons_enabled(False) # Disable all by default
        self.btn_install_to_usb.hide()
        self.btn_delete_local.hide()
        self.btn_delete_from_usb.hide()

    def update_for_local_file(self, file_path: Path, usb_drive_selected: bool):
        self.clear_card_content()
        self.current_local_file_path = file_path

        self.title_label.setText(f"Локальный: {file_path.name}")
        self.title_label.setToolTip(file_path.name)

        size_gb = file_path.stat().st_size / (1024**3)
        self.info_layout.addRow("Имя файла:", QLabel(file_path.name))
        path_label = QLabel(str(file_path))
        path_label.setWordWrap(True)
        self.info_layout.addRow("Полный путь:", path_label)
        self.info_layout.addRow("Размер:", QLabel(f"{size_gb:.2f} GB"))
        self.info_layout.addRow("Тип:", QLabel(file_path.suffix.lstrip('.').upper()))

        self.btn_install_to_usb.show()
        self.btn_install_to_usb.setEnabled(usb_drive_selected)
        self.btn_delete_local.show()
        self.btn_delete_local.setEnabled(True)
        self.btn_delete_from_usb.hide()

    def update_for_usb_game(self, game: FlashGame):
        self.clear_card_content()
        self.current_flash_game = game

        self.title_label.setText(f"На USB: {game.display_title}")
        self.title_label.setToolTip(game.display_title)

        size_gb = game.size / (1024**3)
        self.info_layout.addRow("ID Игры:", QLabel(game.id if hasattr(game, 'id') else "N/A"))
        path_label = QLabel(str(game.dir)) # Changed game.path to game.dir
        path_label.setWordWrap(True)
        self.info_layout.addRow("Путь на USB:", path_label)
        self.info_layout.addRow("Размер:", QLabel(f"{size_gb:.2f} GB"))

        self.btn_install_to_usb.hide()
        self.btn_delete_local.hide()
        self.btn_delete_from_usb.show()
        self.btn_delete_from_usb.setEnabled(True)

    def set_buttons_enabled(self, enabled: bool):
        """Enable or disable all action buttons on the card."""
        self.btn_install_to_usb.setEnabled(enabled and self.current_local_file_path is not None and self.main_window.current_usb_drive is not None)
        self.btn_delete_local.setEnabled(enabled and self.current_local_file_path is not None)
        self.btn_delete_from_usb.setEnabled(enabled and self.current_flash_game is not None)


# ---------------------------------------------------------------------------
# 💾 USB Copy Thread
# ---------------------------------------------------------------------------
class CopyFilesThread(QThread):
    """Thread for copying files to USB with progress."""
    # current_file_name, percentage, speed_mbps, eta_str
    copy_progress = Signal(str, int, float, str)
    copy_finished = Signal(bool, str) # success, message

    def __init__(self, drive_manager: Drive, source_paths: List[Path], parent=None):
        super().__init__(parent)
        self.drive_manager = drive_manager
        self.source_paths = source_paths
        self.is_cancelled = False

    def run(self):
        try:
            # This callback will be called by EnhancedDrive.add_games_with_progress
            def _emit_thread_progress(copy_progress_obj: Drive.CopyProgress): # Use Drive.CopyProgress
                if self.is_cancelled:
                    # If drive manager's operation supports cancellation, it should raise an error or stop.
                    # This is a fallback check.
                    raise InterruptedError("Copy operation cancelled by user.")

                percent = 0
                if copy_progress_obj.total_bytes > 0:
                    percent = int((copy_progress_obj.bytes_copied / copy_progress_obj.total_bytes) * 100)

                eta_str = self.format_time(copy_progress_obj.eta_seconds)
                self.copy_progress.emit(
                    copy_progress_obj.current_file,
                    percent,
                    copy_progress_obj.speed_mbps,
                    eta_str
                )

            # Assuming add_games_with_progress calls the callback frequently
            # and can be interrupted if the callback raises an exception.
            # Also, EnhancedDrive itself would need a mechanism to stop its internal loops if is_cancelled is set.
            # For now, we rely on the callback exception.
            success = self.drive_manager.add_games_with_progress(self.source_paths, _emit_thread_progress)

            if self.is_cancelled: # Check after the operation
                self.copy_finished.emit(False, "Копирование отменено.")
            elif success:
                self.copy_finished.emit(True, f"Успешно скопировано {len(self.source_paths)} файлов.")
            else:
                # This 'else' might not be reached if add_games_with_progress raises its own errors for partial failures
                self.copy_finished.emit(False, "Не удалось скопировать некоторые или все файлы.")
        except InterruptedError:
             self.copy_finished.emit(False, "Копирование отменено пользователем.")
        except Exception as e:
            self.copy_finished.emit(False, f"Ошибка при копировании: {e}")

    def cancel(self):
        self.is_cancelled = True
        # If EnhancedDrive had a method like `drive_manager.cancel_copy()`, call it here.

    def format_time(self, seconds: float) -> str:
        if seconds == float('inf') or seconds < 0 or not isinstance(seconds, (int, float)):
            return "..."
        if seconds < 60:
            return f"{int(seconds)} сек"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes} мин {secs} сек"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours} ч {minutes} мин"

    # --- Copy Operations ---
    def _start_copy_to_usb(self, source_file_paths: List[Path]):
        if not self.current_usb_drive:
            QMessageBox.warning(self, "Копирование на USB", "USB диск не выбран.")
            return
        if not source_file_paths:
            QMessageBox.information(self, "Копирование на USB", "Файлы для копирования не выбраны.")
            return

        # Disable buttons during copy
        self.manager_card.set_buttons_enabled(False)
        if ENHANCED_DRIVE_AVAILABLE:
            self.btn_import_external.setEnabled(False)
            self.drive_combo.setEnabled(False)
            self.btn_refresh_drives.setEnabled(False)

        self.manager_progress_bar.setValue(0)
        self.manager_progress_bar.setFormat("Подготовка к копированию...")
        self.manager_progress_bar.show()
        self.status.showMessage(f"Копирование {len(source_file_paths)} файлов на {self.current_usb_drive.name}...")

        self.copy_thread = CopyFilesThread(self.current_usb_drive, source_file_paths, self)
        self.copy_thread.copy_progress.connect(self._on_copy_progress)
        self.copy_thread.copy_finished.connect(self._on_copy_finished)
        self.copy_thread.start()

    @Slot(str, int, float, str) # current_file_name, percentage, speed_mbps, eta_str
    def _on_copy_progress(self, file_name: str, percent: int, speed: float, eta: str):
        self.manager_progress_bar.setValue(percent)
        self.manager_progress_bar.setFormat(f"{file_name}: {percent}% ({speed:.2f} MB/s, ETA: {eta})")

    @Slot(bool, str) # success, message
    def _on_copy_finished(self, success: bool, message: str):
        self.manager_progress_bar.hide()
        self.status.showMessage(message)
        if success:
            QMessageBox.information(self, "Копирование завершено", message)
            self._refresh_usb_games_list() # Refresh list of games on USB
        else:
            QMessageBox.critical(self, "Ошибка копирования", message)

        # Re-enable buttons
        self.manager_card.set_buttons_enabled(True) # This method needs to be added to ManagerGameCard
        if ENHANCED_DRIVE_AVAILABLE:
            self.btn_import_external.setEnabled(True if self.current_usb_drive else False)
            self.drive_combo.setEnabled(True)
            self.btn_refresh_drives.setEnabled(True)


    def closeEvent(self, event):
        """Handle application close events."""
        self.status.showMessage("Сохранение данных и выход...")
        # Attempt to gracefully stop any ongoing download
        if self.queue._is_downloading:
            self.queue.cancel_current_download() # Signal to stop
            # Give a very short time for the thread to potentially acknowledge
            # In a real scenario, might wait a bit longer or use a more robust shutdown
            QTimer.singleShot(500, lambda: self._finalize_close(event))
            event.ignore() # Ignore immediate close, wait for finalize
            return
        self._finalize_close(event)

    def _finalize_close(self, event):
        """Final steps before closing application."""
        if hasattr(self, 'db'): # Check if db was initialized
            self.db.save_database()
        print("Wii Unified Manager closed.")
        event.accept()


###############################################################################
# 🚀 main                                                                    #
###############################################################################

def main():
    app = QApplication(sys.argv)
    # Apply some global settings for better looks if possible
    app.setStyle("Fusion") # Or "Windows", "macOS". Fusion is often a good cross-platform choice.

    # It's good practice to set these for QSettings, etc.
    app.setOrganizationName("MyWiiTools")
    app.setApplicationName("WiiUnifiedManager")

    win = WiiUnifiedManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
