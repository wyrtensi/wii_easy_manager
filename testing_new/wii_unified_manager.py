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
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Slot,
    QTimer,
    Signal,
)
from PySide6.QtGui import QIcon, QPixmap
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
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QComboBox,
    QWidget,
)

# ────────────────────────────────────────────────────────────────────────────
# Local modules
# ────────────────────────────────────────────────────────────────────────────
from wum_style import build_style, WII_BLUE, WII_GRAY, WII_WHITE, WII_GREEN  # type: ignore
from download_queue_class import DownloadQueue  # type: ignore
from wii_game_parser import WiiGame, WiiGameParser  # type: ignore

###############################################################################
# 🎴 GameCard                                                                #
###############################################################################

class GameCard(QWidget):
    """Отображает подробности об игре и кнопку скачивания."""

    def __init__(self, queue: DownloadQueue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue = queue
        # self.setFixedWidth(560) # Removed fixed width

        # ─── заголовок
        self._title = QLabel("Выберите игру слева ✨")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_BLUE};"
            "border-radius:16px;padding:12px;font-size:16pt;font-weight:bold;"
        )

        # ─── обложка
        self._cover = QLabel()
        self._cover.setMinimumSize(200, 200) # Changed from setFixedSize
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet(
            f"background:{WII_GRAY};border:2px dashed {WII_BLUE};border-radius:24px;"
        )
        self._cover.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


        # ─── описание
        self._desc = QLabel("Описание появится здесь…")
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._desc.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_GRAY};"
            "border-radius:16px;padding:12px;"
        )
        self._desc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Allow description to expand

        # ─── кнопка скачивания + прогресс
        self._btn_dl = QPushButton("⬇️ Скачать")
        self._progress = QProgressBar()
        self._progress.hide()
        
        # ─── информация о скорости и времени
        self._speed_label = QLabel("")
        self._speed_label.setAlignment(Qt.AlignCenter)
        self._speed_label.setStyleSheet(
            f"background:{WII_WHITE};border:1px solid {WII_GRAY};"
            "border-radius:8px;padding:6px;font-size:12pt;"
        )
        self._speed_label.hide()

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._cover, 0, Qt.AlignCenter) # Stretch factor 0 for cover
        lay.addWidget(self._btn_dl, 0, Qt.AlignCenter) # Stretch factor 0 for button
        lay.addWidget(self._progress, 0) # Stretch factor 0 for progress
        lay.addWidget(self._speed_label, 0) # Stretch factor 0 for speed info
        lay.addWidget(self._desc, 1) # Stretch factor 1 for description to take remaining space

        # Connect signals
        self._btn_dl.clicked.connect(self._do_download)
        queue.download_started.connect(self._on_dl_start)
        queue.download_finished.connect(self._on_dl_finish)
        queue.progress_changed.connect(self._on_progress)
        
        # Подключаем новый сигнал для скорости
        if hasattr(queue, 'speed_updated'):
            queue.speed_updated.connect(self._on_speed_update)

        self._game: Optional[WiiGame] = None

    # ------------------------------------------------------------------
    def _refresh_btn(self):
        if not self._game:
            self._btn_dl.setEnabled(False)
            self._btn_dl.setText("⬇️ Скачать")
            return
        status = getattr(self._game, "status", "")
        self._btn_dl.setEnabled(status not in {"queued", "downloading", "downloaded"})
        self._btn_dl.setText({
            "queued": "⌛ В очереди",
            "downloading": "⬇️ Скачивается…",
            "downloaded": "✅ Скачано",
        }.get(status, "⬇️ Скачать"))

    # ------------------------------------------------------------------
    def _do_download(self):
        if self._game:
            self.queue.add(self._game)
            self._refresh_btn()

    # ------------------------------------------------------------------
    @Slot(WiiGame)
    def _on_dl_start(self, g: WiiGame):
        if self._game and g.title == self._game.title:
            self._progress.show()
            self._progress.setValue(0)
            self._speed_label.show()
            self._speed_label.setText("Подготовка к загрузке...")
            self._refresh_btn()

    @Slot(WiiGame)
    def _on_dl_finish(self, g: WiiGame):
        if self._game and g.title == self._game.title:
            self._progress.hide()
            self._speed_label.hide()
            self._refresh_btn()

    @Slot(WiiGame, int)
    def _on_progress(self, g: WiiGame, percent: int):
        if self._game and g.title == self._game.title:
            self._progress.setValue(percent)
    
    @Slot(WiiGame, float, str)
    def _on_speed_update(self, g: WiiGame, speed: float, eta: str):
        """Обновление информации о скорости и времени"""
        if self._game and g.title == self._game.title:
            speed_text = f"⚡ {speed:.1f} МБ/с | ⏱️ {eta}"
            self._speed_label.setText(speed_text)

    # ------------------------------------------------------------------
    def update_game(self, game: WiiGame):
        self._game = game
        self._title.setText(game.title)
        
        # Показываем основную информацию сразу
        basic_info = f"Регион: {game.region}\n"
        if hasattr(game, 'rating') and game.rating:
            basic_info += f"Рейтинг: {game.rating}\n"
        if hasattr(game, 'serial') and game.serial:
            basic_info += f"Серийный номер: {game.serial}\n"
        if hasattr(game, 'year') and game.year:
            basic_info += f"Год: {game.year}\n"
        if hasattr(game, 'players') and game.players:
            basic_info += f"Игроки: {game.players}\n"
        if hasattr(game, 'file_size') and game.file_size:
            basic_info += f"Размер файла: {game.file_size}\n"
            
        # Если есть детальная информация, показываем её
        if hasattr(game, 'graphics') and game.graphics:
            basic_info += f"\nГрафика: {game.graphics}\n"
        if hasattr(game, 'sound') and game.sound:
            basic_info += f"Звук: {game.sound}\n"
        if hasattr(game, 'gameplay') and game.gameplay:
            basic_info += f"Геймплей: {game.gameplay}\n"
        if hasattr(game, 'overall') and game.overall:
            basic_info += f"Общая оценка: {game.overall}\n"
        if hasattr(game, 'verified') and game.verified:
            basic_info += f"Проверено: {game.verified}\n"
        
        # Если детальной информации нет, загружаем её
        if not (hasattr(game, 'graphics') and game.graphics):
            basic_info += "\nЗагружается детальная информация..."
            self._load_detailed_info_async(game)
        
        self._desc.setText(basic_info)
        
        # Загружаем обложку
        if hasattr(game, 'box_art') and game.box_art:
            self._load_cover_image_sync(game.box_art)
        else:
            self._load_cover_image_by_id(game)
        
        self._refresh_btn()

    def _load_detailed_info_async(self, game: WiiGame):
        """Загружает детальную информацию асинхронно"""
        def load_details():
            try:
                from wii_game_parser import WiiGameParser
                parser = WiiGameParser()
                
                detailed_game = parser.parse_game_details_from_url(game.detail_url)
                if detailed_game:
                    # Обновляем игру с детальной информацией
                    for attr in ['serial', 'players', 'year', 'graphics', 'sound', 
                                'gameplay', 'overall', 'crc', 'verified', 'file_size',
                                'download_url', 'box_art', 'disc_art']:
                        if hasattr(detailed_game, attr):
                            setattr(game, attr, getattr(detailed_game, attr))
                    
                    # Обновляем UI в главном потоке
                    QTimer.singleShot(0, lambda: self.update_game(game))
                        
            except Exception as e:
                print(f"Ошибка загрузки деталей: {e}")
                QTimer.singleShot(0, lambda: self._desc.setText(
                    f"Регион: {game.region}\nОшибка загрузки детальной информации: {e}"
                ))
        
        import threading
        threading.Thread(target=load_details, daemon=True).start()

    def _load_cover_image_sync(self, image_url: str):
        """Загружает обложку синхронно"""
        self._cover.setText("🖼️ Загрузка...")
        
        def load_image():
            try:
                import requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://vimm.net/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                }
                
                response = requests.get(image_url, headers=headers, timeout=10, verify=False)
                response.raise_for_status()
                
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp.write(response.content)
                    temp_path = tmp.name
                
                QTimer.singleShot(0, lambda: self._set_cover_image(temp_path))
                
            except Exception as e:
                print(f"Ошибка загрузки обложки: {e}")
                QTimer.singleShot(0, lambda: self._cover.setText("🖼️ (ошибка)"))
        
        import threading
        threading.Thread(target=load_image, daemon=True).start()

    def _load_cover_image_by_id(self, game: WiiGame):
        """Загружает обложку по ID игры"""
        import re
        id_match = re.search(r'/vault/(\d+)', game.detail_url)
        if id_match:
            game_id = id_match.group(1)
            # Пробуем основной URL обложки
            primary_url = f"https://dl.vimm.net/image.php?type=box&id={game_id}"
            self._load_cover_image_sync(primary_url)
        else:
            self._cover.setText("🖼️ (нет ID)")

    def _set_cover_image(self, image_path: str):
        """Устанавливает изображение обложки"""
        try:
            target_width = self._cover.width() - 10
            if target_width < 50:
                target_width = 200
            
            pix = QPixmap(image_path)
            if not pix.isNull():
                scaled_pix = pix.scaledToWidth(target_width, Qt.SmoothTransformation)
                self._cover.setPixmap(scaled_pix)
            else:
                self._cover.setText("🖼️ (err)")
                
            # Удаляем временный файл
            try:
                import os
                os.unlink(image_path)
            except Exception:
                pass
                
        except Exception as e:
            print(f"Ошибка установки обложки: {e}")
            self._cover.setText("🖼️ (err)")

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
        self._original_geometry = None
        self._is_scaled = False

    def showEvent(self, e):  # noqa: N802
        super().showEvent(e)
        # Запоминаем оригинальную геометрию при первом показе
        if self._original_geometry is None:
            self._original_geometry = self.geometry()

    def enterEvent(self, e):  # noqa: N802
        if not self.isChecked() and not self._is_scaled:
            self._scale(1.05)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        if not self.isChecked() and self._is_scaled:
            self._scale(1.0)
        super().leaveEvent(e)

    def _scale(self, k: float):
        if self._original_geometry is None:
            return
            
        self._anim.stop()
        current_rect = self.geometry()
        
        if k == 1.0:
            # Возвращаемся к оригинальному размеру
            target_rect = self._original_geometry
            self._is_scaled = False
        else:
            # Увеличиваем относительно оригинального размера
            orig_center = self._original_geometry.center()
            new_width = int(self._original_geometry.width() * k)
            new_height = int(self._original_geometry.height() * k)
            target_rect = QRectF(
                orig_center.x() - new_width/2,
                orig_center.y() - new_height/2,
                new_width,
                new_height
            ).toRect()
            self._is_scaled = True
        
        self._anim.setStartValue(current_rect)
        self._anim.setEndValue(target_rect)
        self._anim.start()

###############################################################################
# � FlashGameCard                                                           #
###############################################################################

class FlashGameCard(QWidget):
    """Карточка для отображения игры с флешки."""

    def __init__(self, manager_window):
        super().__init__()
        self.manager = manager_window
        self.current_game = None
        
        # ─── заголовок
        self._title = QLabel("Выберите игру слева 💾")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_BLUE};"
            "border-radius:16px;padding:12px;font-size:16pt;font-weight:bold;"
        )

        # ─── обложка/иконка
        self._cover = QLabel()
        self._cover.setMinimumSize(200, 200)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet(
            f"background:{WII_GRAY};border:2px dashed {WII_BLUE};border-radius:24px;"
        )
        self._cover.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ─── описание/информация
        self._info = QLabel("Информация об игре появится здесь…")
        self._info.setWordWrap(True)
        self._info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._info.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_GRAY};"
            "border-radius:16px;padding:12px;"
        )
        self._info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ─── кнопка удаления
        self._btn_remove = QPushButton("🗑️ Удалить с флешки")
        self._btn_remove.setEnabled(False)
        
        # ─── дополнительные кнопки
        self._btn_open_folder = QPushButton("📂 Открыть папку")
        self._btn_open_folder.setEnabled(False)

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._cover, 0, Qt.AlignCenter)
        lay.addWidget(self._info, 1)
        
        # Кнопки в ряд
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._btn_remove)
        btn_layout.addWidget(self._btn_open_folder)
        lay.addLayout(btn_layout)

        # Подключаем сигналы
        self._btn_remove.clicked.connect(self._remove_game)
        self._btn_open_folder.clicked.connect(self._open_folder)

    def update_game(self, game):
        """Обновить информацию об игре"""
        self.current_game = game
        
        if game is None:
            self._title.setText("Выберите игру слева 💾")
            self._cover.setText("💾")
            self._info.setText("Информация об игре появится здесь…")
            self._btn_remove.setEnabled(False)
            self._btn_open_folder.setEnabled(False)
            return
        
        # Заголовок
        self._title.setText(f"💾 {game.display_title}")
        
        # Информация
        info_text = f"🆔 ID: {game.id}\n"
        info_text += f"📁 Размер: {game.size / (1024**3):.2f} ГБ\n"
        
        if hasattr(game, 'dir'):
            info_text += f"📂 Путь: {game.dir}\n"
        
        # Определяем регион по ID
        if len(game.id) >= 4:
            region_code = game.id[3]
            region_map = {
                'E': '🇺🇸 USA',
                'P': '🇪🇺 Europe', 
                'J': '🇯🇵 Japan',
                'K': '🇰🇷 Korea'
            }
            region = region_map.get(region_code, '🌐 Unknown')
            info_text += f"🌍 Регион: {region}\n"
        
        # Статус проверки
        info_text += f"\n✅ Игра установлена на флешке"
        
        self._info.setText(info_text)
        
        # Обложка/иконка
        self._cover.setText("💾\n🎮")
        
        # Активируем кнопки
        self._btn_remove.setEnabled(True)
        self._btn_open_folder.setEnabled(True)

    def _remove_game(self):
        """Удалить игру с флешки"""
        if self.current_game:
            self.manager._remove_flash_game(self.current_game)

    def _open_folder(self):
        """Открыть папку с игрой"""
        if self.current_game and hasattr(self.current_game, 'dir'):
            import subprocess
            import os
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(str(self.current_game.dir))
                else:  # Linux/Mac
                    subprocess.run(['xdg-open', str(self.current_game.dir)])
            except Exception as e:
                print(f"Не удалось открыть папку: {e}")

###############################################################################
# �🖥️ Main window                                                             #
###############################################################################

class WiiUnifiedManager(QMainWindow):
    """Главное окно приложения."""

    # Сигнал для обновления списка из потока
    search_completed = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("🎮 Wii Unified Manager 2.4")
        self.resize(1280, 860)
        self.setWindowIcon(QIcon())
        self.setStyleSheet(build_style())

        # Services
        self.parser = WiiGameParser()
        self.queue = DownloadQueue(self)

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
        self.stack.addWidget(self.page_search) # Add pages to stack
        self.stack.addWidget(self.page_manager)
        root.addWidget(self.stack, 1) # Add stack to root layout with stretch factor

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Готов к работе 🔋")

        self._games: List[WiiGame] = []
        self._flash_games = []  # Список игр с флешки
        self.current_drive = None  # Текущая выбранная флешка
        self._connect_signals()
        
        # Подключаем сигнал поиска
        self.search_completed.connect(self._populate_list)

    # ------------------------------------------------------------------
    def _build_search_page(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)

        hbox = QHBoxLayout()
        self.edit_query = QLineEdit()
        self.edit_query.setPlaceholderText("Введите название игры…")
        self.btn_go = QPushButton("🔍 Найти")
        hbox.addWidget(self.edit_query)
        hbox.addWidget(self.btn_go)
        vbox.addLayout(hbox)

        splitter = QSplitter(Qt.Horizontal)
        self.list_results = QListWidget()
        self.card = GameCard(self.queue) # GameCard will now fill available space
        splitter.addWidget(self.list_results)
        splitter.addWidget(self.card)
        splitter.setSizes([350, 650]) # Adjusted sizes: left (search) narrower, right (card) wider
        splitter.setStretchFactor(0, 1) # Search results list (left pane)
        splitter.setStretchFactor(1, 2) # Game card (right pane) - give it more weight
        vbox.addWidget(splitter, 1) # Add splitter with stretch factor to fill vertical space
        return page

    # ------------------------------------------------------------------
    def _build_manager_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Drive selection header
        drive_layout = QHBoxLayout()
        drive_label = QLabel("💾 Флешка:")
        drive_label.setStyleSheet("font-size:16pt;font-weight:bold;color:#5C6BC0;")
        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(200)
        self.drive_combo.setStyleSheet(
            f"QComboBox {{ font-size:14pt; padding:8px; border:2px solid {WII_GRAY}; "
            f"border-radius:12px; background:{WII_WHITE}; }}"
        )
        
        self.btn_refresh_drives = QPushButton("🔄 Обновить")
        self.drive_info_label = QLabel("")
        self.drive_info_label.setStyleSheet("font-size:12pt;color:#666;")
        
        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.drive_combo, 1)
        drive_layout.addWidget(self.btn_refresh_drives)
        drive_layout.addStretch()
        drive_layout.addWidget(self.drive_info_label)
        layout.addLayout(drive_layout)

        # Downloads status section
        downloads_layout = QHBoxLayout()
        downloads_label = QLabel("📥 Активные загрузки:")
        downloads_label.setStyleSheet("font-size:14pt;font-weight:bold;color:#5C6BC0;")
        self.downloads_info = QLabel("Нет активных загрузок")
        self.downloads_info.setStyleSheet("font-size:12pt;color:#666;")
        
        downloads_layout.addWidget(downloads_label)
        downloads_layout.addStretch()
        downloads_layout.addWidget(self.downloads_info)
        layout.addLayout(downloads_layout)

        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - games list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Search for downloaded games
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Поиск:")
        self.flash_search = QLineEdit()
        self.flash_search.setPlaceholderText("Поиск среди игр...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.flash_search)
        left_layout.addLayout(search_layout)
        
        # Games list
        self.list_flash_games = QListWidget()
        self.list_flash_games.setMinimumWidth(300)
        left_layout.addWidget(self.list_flash_games, 1)
        
        # Action buttons
        buttons_layout = QVBoxLayout()
        self.btn_add_external = QPushButton("📂 Добавить внешние файлы")
        self.btn_copy_downloaded = QPushButton("💾 Скопировать скачанное")
        self.btn_remove_from_flash = QPushButton("🗑️ Удалить с флешки")
        self.btn_verify_games = QPushButton("🔍 Проверить игры")
        
        buttons_layout.addWidget(self.btn_add_external)
        buttons_layout.addWidget(self.btn_copy_downloaded)
        buttons_layout.addWidget(self.btn_remove_from_flash)
        buttons_layout.addWidget(self.btn_verify_games)
        buttons_layout.addStretch()
        
        left_layout.addLayout(buttons_layout)
        splitter.addWidget(left_widget)

        # Right side - game card
        self.flash_card = FlashGameCard(self)
        splitter.addWidget(self.flash_card)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)

        # Progress bar for operations
        self.flash_progress = QProgressBar()
        self.flash_progress.setVisible(False)
        self.flash_progress.setStyleSheet(
            f"QProgressBar {{ border:2px solid {WII_GRAY}; border-radius:12px; "
            f"text-align:center; font-size:14pt; min-height:32px; }}"
            f"QProgressBar::chunk {{ background-color:{WII_GREEN}; border-radius:10px; }}"
        )
        layout.addWidget(self.flash_progress)

        return page

    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.btn_search.clicked.connect(lambda: self._switch_page(self.page_search, self.btn_search))
        self.btn_manager.clicked.connect(lambda: self._switch_page(self.page_manager, self.btn_manager))

        # Manager page signals
        self.btn_refresh_drives.clicked.connect(self._refresh_drives)
        self.drive_combo.currentIndexChanged.connect(self._on_drive_selected)
        self.btn_add_external.clicked.connect(self._action_add_external_to_usb)
        self.btn_copy_downloaded.clicked.connect(self._action_copy_downloaded_to_usb)
        self.btn_remove_from_flash.clicked.connect(self._action_remove_from_usb)
        self.btn_verify_games.clicked.connect(self._action_verify_games)
        
        # Flash games list selection
        self.list_flash_games.currentRowChanged.connect(self._flash_game_selected)
        
        # Search in flash games
        self.flash_search.textChanged.connect(self._filter_flash_games)

        # Search page signals
        self.btn_go.clicked.connect(self._do_search)
        self.edit_query.returnPressed.connect(self._do_search)
        self.list_results.currentRowChanged.connect(self._row_changed)

        # Queue → status
        # Ensure self.queue is initialized before connecting its signals. It is in __init__.
        if hasattr(self, 'queue') and self.queue: # Check if queue exists
            self.queue.queue_changed.connect(lambda n: self.status.showMessage(f"Очередь: {n} игр"))
            self.queue.download_started.connect(lambda g: self.status.showMessage(f"⬇️ Скачивание: {g.title}…"))
            self.queue.download_finished.connect(lambda g: self.status.showMessage(f"✅ Завершено: {g.title}"))
            
            # Подключаем сигналы для обновления информации о загрузках
            self.queue.queue_changed.connect(self._update_downloads_info)
            self.queue.download_started.connect(self._update_downloads_info)
            self.queue.download_finished.connect(self._update_downloads_info)
            
            # Подключаем сигнал скорости для обновления статуса
            if hasattr(self.queue, 'speed_updated'):
                self.queue.speed_updated.connect(self._on_speed_update)
        else:
            print("Warning: DownloadQueue not initialized when connecting signals.")

    def _on_speed_update(self, game: WiiGame, speed: float, eta: str):
        """Обновление статуса с информацией о скорости"""
        self.status.showMessage(f"⬇️ {game.title}: {speed:.1f} МБ/с, осталось {eta}")

    def _update_downloads_info(self, *args):
        """Обновление информации о загрузках"""
        try:
            queue_size = self.queue._queue.qsize()
            active_downloads = len(self.queue._downloads_in_progress)
            
            if active_downloads == 0 and queue_size == 0:
                self.downloads_info.setText("Нет активных загрузок")
                self.downloads_info.setStyleSheet("font-size:12pt;color:#666;")
            else:
                info_text = ""
                if active_downloads > 0:
                    info_text += f"🔄 Скачивается: {active_downloads}"
                if queue_size > 0:
                    if info_text:
                        info_text += " | "
                    info_text += f"⏳ В очереди: {queue_size}"
                
                self.downloads_info.setText(info_text)
                self.downloads_info.setStyleSheet("font-size:12pt;color:#66BB6A;font-weight:bold;")
        except Exception as e:
            print(f"Ошибка обновления информации о загрузках: {e}")

    # ------------------------------------------------------------------
    def _flash_game_selected(self, row: int):
        """Обработка выбора игры с флешки"""
        if 0 <= row < len(self._flash_games):
            game = self._flash_games[row]
            self.flash_card.update_game(game)
        else:
            self.flash_card.update_game(None)

    def _filter_flash_games(self, text: str):
        """Фильтрация игр с флешки по тексту поиска"""
        # Простая фильтрация - скрываем элементы, которые не соответствуют поиску
        search_text = text.lower()
        for i in range(self.list_flash_games.count()):
            item = self.list_flash_games.item(i)
            if item:
                game_text = item.text().lower()
                item.setHidden(search_text not in game_text)


    # ------------------------------------------------------------------
    def _switch_page(self, page: QWidget, btn: QPushButton):
        self.btn_search.setChecked(False)
        self.btn_manager.setChecked(False)
        # Also visually reset other buttons if they were animated/scaled
        if btn != self.btn_search:
            self.btn_search._scale(1.0)
        if btn != self.btn_manager:
            self.btn_manager._scale(1.0)

        btn.setChecked(True)
        btn._scale(1.0) # Ensure checked button is at normal scale
        self.stack.setCurrentWidget(page)
        if page == self.page_manager:
            self._refresh_drives() # Refresh drives when switching to manager page

    # Методы для работы с флешкой
    def _refresh_drives(self):
        """Обновить список дисков"""
        self.drive_combo.clear()
        self.current_drive = None
        self.drive_info_label.setText("")
        
        try:
            # Импортируем enhanced drive
            from wii_download_manager.models.enhanced_drive import EnhancedDrive
            drives = EnhancedDrive.get_drives()
            
            if not drives:
                self.drive_combo.addItem("Нет доступных дисков")
                self.status.showMessage("Съемные диски не найдены")
                return
            
            for drive in drives:
                display_text = f"{drive.name} ({drive.available_space}/{drive.total_space} ГБ)"
                self.drive_combo.addItem(display_text, drive)
            
            self.status.showMessage(f"Найдено {len(drives)} съемных дисков")
            
            # Автоматически выбираем первый диск
            if drives:
                self.drive_combo.setCurrentIndex(0)
                self._on_drive_selected()
                
        except Exception as e:
            print(f"Ошибка при обновлении дисков: {e}")
            self.drive_combo.addItem("Ошибка загрузки дисков")
            self.status.showMessage(f"Ошибка: {e}")

    def _on_drive_selected(self):
        """Обработка выбора диска"""
        current_index = self.drive_combo.currentIndex()
        self.current_drive = self.drive_combo.itemData(current_index)
        
        if self.current_drive:
            # Обновляем информацию о диске
            space_info = self.current_drive.get_space_info()
            info_text = f"💾 {space_info['free_gb']:.1f} ГБ свободно из {space_info['total_gb']:.1f} ГБ"
            self.drive_info_label.setText(info_text)
            
            # Загружаем игры
            self._load_flash_games()
            self.status.showMessage(f"Выбрана флешка: {self.current_drive.name}")
        else:
            self.drive_info_label.setText("")
            self._flash_games.clear()
            self.list_flash_games.clear()
            self.flash_card.update_game(None)

    def _load_flash_games(self):
        """Загрузить игры с флешки"""
        if not self.current_drive:
            return
            
        try:
            self._flash_games = self.current_drive.get_games()
            self._update_flash_games_list()
            
            games_info = self.current_drive.get_games_info()
            self.status.showMessage(
                f"Загружено {games_info['total_games']} игр "
                f"({games_info['total_size_gb']:.1f} ГБ)"
            )
            
        except Exception as e:
            print(f"Ошибка загрузки игр с флешки: {e}")
            self.status.showMessage(f"Ошибка загрузки игр: {e}")
            self._flash_games.clear()
            self.list_flash_games.clear()

    def _update_flash_games_list(self):
        """Обновить список игр с флешки"""
        self.list_flash_games.clear()
        
        for game in self._flash_games:
            # Добавляем эмодзи для региона
            region_emoji = "🌐"
            if len(game.id) >= 4:
                region_code = game.id[3]
                region_emojis = {
                    'E': '🇺🇸',
                    'P': '🇪🇺', 
                    'J': '🇯🇵',
                    'K': '🇰🇷'
                }
                region_emoji = region_emojis.get(region_code, '🌐')
            
            display_text = f"{region_emoji} {game.display_title}"
            size_gb = game.size / (1024**3)
            display_text += f" ({size_gb:.1f} ГБ)"
            
            item = QListWidgetItem(display_text)
            self.list_flash_games.addItem(item)
        
        # Сбрасываем выбор карточки
        self.flash_card.update_game(None)

    def _action_add_external_to_usb(self):
        """Добавить внешние игры на флешку"""
        if not self.current_drive:
            self.status.showMessage("Сначала выберите флешку")
            return
            
        from PySide6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Выберите файлы игр для добавления на флешку", 
            "", 
            "Файлы игр (*.iso *.wbfs *.rvz);;Все файлы (*)"
        )
        
        if files:
            self._copy_files_to_flash(files)

    def _action_copy_downloaded_to_usb(self):
        """Копировать скачанные игры на флешку"""
        if not self.current_drive:
            self.status.showMessage("Сначала выберите флешку")
            return
            
        # Здесь нужно найти скачанные игры
        # Пока просто покажем сообщение
        self.status.showMessage("Функция копирования скачанных игр будет добавлена")

    def _action_remove_from_usb(self):
        """Удалить выбранную игру с флешки"""
        current_row = self.list_flash_games.currentRow()
        if current_row >= 0 and current_row < len(self._flash_games):
            game = self._flash_games[current_row]
            self._remove_flash_game(game)
        else:
            self.status.showMessage("Выберите игру для удаления")

    def _action_verify_games(self):
        """Проверить целостность игр на флешке"""
        if not self.current_drive:
            self.status.showMessage("Сначала выберите флешку")
            return
            
        try:
            results = self.current_drive.verify_games()
            
            # Показываем результаты
            valid_count = sum(1 for r in results if r['valid'])
            total_count = len(results)
            
            if valid_count == total_count:
                self.status.showMessage(f"✅ Все {total_count} игр прошли проверку")
            else:
                error_count = total_count - valid_count
                self.status.showMessage(
                    f"⚠️ Проверка завершена: {valid_count} OK, {error_count} с ошибками"
                )
                
        except Exception as e:
            self.status.showMessage(f"Ошибка проверки: {e}")

    def _copy_files_to_flash(self, file_paths):
        """Копировать файлы на флешку"""
        if not self.current_drive:
            return
            
        try:
            # Показываем прогресс
            self.flash_progress.setVisible(True)
            self.flash_progress.setValue(0)
            
            # Проверяем место на диске
            total_size = 0
            valid_files = []
            
            for file_path in file_paths:
                from pathlib import Path
                path = Path(file_path)
                if path.exists():
                    total_size += path.stat().st_size
                    valid_files.append(path)
            
            space_info = self.current_drive.get_space_info()
            if total_size > space_info['free_bytes']:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Недостаточно места",
                    f"Нужно: {total_size / (1024**3):.1f} ГБ\n"
                    f"Доступно: {space_info['free_gb']:.1f} ГБ"
                )
                self.flash_progress.setVisible(False)
                return
            
            # Запускаем копирование в отдельном потоке
            self._start_copy_operation(valid_files)
            
        except Exception as e:
            self.status.showMessage(f"Ошибка подготовки копирования: {e}")
            self.flash_progress.setVisible(False)

    def _start_copy_operation(self, files):
        """Запустить операцию копирования"""
        def progress_callback(progress):
            """Callback для обновления прогресса"""
            if progress.total_files > 0:
                percent = int((progress.files_completed / progress.total_files) * 100)
                QTimer.singleShot(0, lambda: self.flash_progress.setValue(percent))
                
                status_text = f"Копирование: {progress.current_file} ({progress.files_completed}/{progress.total_files})"
                QTimer.singleShot(0, lambda: self.status.showMessage(status_text))
        
        def copy_worker():
            """Рабочий поток для копирования"""
            try:
                success = self.current_drive.add_games_with_progress(files, progress_callback)
                QTimer.singleShot(0, lambda: self._on_copy_finished(success))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_copy_error(str(e)))
        
        import threading
        thread = threading.Thread(target=copy_worker, daemon=True)
        thread.start()

    def _on_copy_finished(self, success):
        """Обработка завершения копирования"""
        self.flash_progress.setVisible(False)
        
        if success:
            self.status.showMessage("✅ Копирование завершено успешно")
            self._load_flash_games()  # Перезагружаем список игр
        else:
            self.status.showMessage("⚠️ Копирование завершено с ошибками")

    def _on_copy_error(self, error_message):
        """Обработка ошибки копирования"""
        self.flash_progress.setVisible(False)
        self.status.showMessage(f"❌ Ошибка копирования: {error_message}")

    def _remove_flash_game(self, game):
        """Удалить игру с флешки"""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Вы действительно хотите удалить игру '{game.display_title}' с флешки?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Удаляем игру
                game.delete()
                
                # Обновляем интерфейс
                self._load_flash_games()
                self.flash_card.update_game(None)
                
                self.status.showMessage(f"✅ Игра '{game.display_title}' удалена с флешки")
                
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", 
                    f"Не удалось удалить игру: {e}"
                )
                self.status.showMessage(f"❌ Ошибка удаления: {e}")


    # ------------------------------------------------------------------
    def _do_search(self):
        query = self.edit_query.text().strip()
        if not query:
            return
        self.status.showMessage(f"Поиск «{query}»…")
        print(f"Начинаем поиск: {query}")

        def worker():
            try:
                print(f"Выполняем поиск для: {query}")
                games = self.parser.search_games_online(query)
                print(f"Найдено игр: {len(games)}")
                # Используем сигнал для передачи результатов в главный поток
                self.search_completed.emit(games)
            except Exception as e:
                print(f"Ошибка поиска: {e}")
                error_msg = f"Ошибка поиска: {e}"
                QTimer.singleShot(0, lambda: self.status.showMessage(error_msg))

        import threading

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    def _populate_list(self, games: List[WiiGame]):
        print(f"_populate_list вызвана с {len(games)} играми")
        self._games = games
        self.list_results.clear()
        for g in games:
            # Добавляем регион к названию игры
            region_emoji = {
                'USA': '🇺🇸',
                'Europe': '🇪🇺', 
                'Japan': '🇯🇵',
                'PAL': '🌍',
                'NTSC': '📺'
            }.get(g.region, '🌐')
            
            display_text = f"{region_emoji} {g.title}"
            if g.region and g.region not in g.title:
                display_text += f" ({g.region})"
                
            item = QListWidgetItem(display_text)
            self.list_results.addItem(item)
        if games:
            self.list_results.setCurrentRow(0)
        self.status.showMessage(f"Найдено {len(games)} игр")
        print(f"Список обновлен, в списке {self.list_results.count()} элементов")

    # ------------------------------------------------------------------
    def _row_changed(self, row: int):
        if 0 <= row < len(self._games):
            self.card.update_game(self._games[row])

###############################################################################
# 🚀 main                                                                    #
###############################################################################

def main():
    app = QApplication(sys.argv)
    win = WiiUnifiedManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
