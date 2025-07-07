#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wii Unified Manager - Объединенный менеджер игр Wii
Красивый интерфейс для поиска, загрузки и управления играми Wii
"""

import sys
import os
import json
import threading
import time
import base64
import requests
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse
from queue import Queue, Empty

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QComboBox, QTextEdit, QSplitter, QTabWidget, QGroupBox,
    QProgressBar, QStatusBar, QMenuBar, QMenu, QFileDialog,
    QMessageBox, QFormLayout,
    QCheckBox, QScrollArea, QFrame, QGridLayout, QStackedWidget,
    QToolButton, QButtonGroup, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QPropertyAnimation, 
    QEasingCurve, QRect, QPoint, QEvent, QUrl
)
from PySide6.QtGui import (
    QPixmap, QIcon, QFont, QAction, QDesktopServices, QPainter,
    QBrush, QColor, QGradient, QLinearGradient, QPen, QFontMetrics
)

# Импортируем наши модули
from wii_game_parser import WiiGameParser, WiiGameDatabase, WiiGame
from wii_game_downloader import WiiGameDownloader
from wii_game_selenium_downloader import WiiGameSeleniumDownloader
from wii_download_manager.models.enhanced_drive import EnhancedDrive as Drive, CopyProgress
from wii_download_manager.models.game import Game as FlashGame

# Глобальные настройки стилей - светлая приятная тема
# Цветовая палитра в более ярком "детском" стиле
WII_BLUE = "#5C6BC0"          # основной синий
WII_LIGHT_BLUE = "#C5CAE9"    # светлый синий для подсветок
WII_WHITE = "#FFFFFF"         # белый
WII_LIGHT_GRAY = "#FAFAFA"    # светло‑серый фон
WII_GRAY = "#E0E0E0"          # серые границы
WII_DARK_GRAY = "#555555"     # тёмный текст
WII_GREEN = "#66BB6A"         # цвет успеха
WII_ORANGE = "#FFB74D"        # цвет наведения
WII_RED = "#EF5350"           # ошибки
WII_YELLOW = "#FFD54F"        # предупреждения

# Стили для интерфейса - светлая приятная тема в стиле Wii
WII_STYLE = f"""
/* Главное окно и базовый виджет */
QMainWindow {{
    background-color: {WII_LIGHT_GRAY};
    font-family: 'Comic Sans MS', 'Segoe UI', sans-serif;
    font-size: 12pt;
}}

QWidget {{
    background-color: transparent;
    color: {WII_DARK_GRAY};
    font-size: 12pt;
}}

/* Крупные кнопки с закругленными краями */
QPushButton {{
    background-color: {WII_BLUE};
    color: white;
    border: none;
    border-radius: 16px;
    padding: 12px 24px;
    font-size: 14pt;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {WII_ORANGE};
}}

QPushButton:pressed {{
    background-color: {WII_GREEN};
}}

QPushButton:disabled {{
    background-color: {WII_GRAY};
    color: {WII_DARK_GRAY};
}}

/* Кнопки навигации */
QPushButton[nav="true"] {{
    background-color: {WII_BLUE};
    border-radius: 20px;
    padding: 14px 28px;
    font-size: 18pt;
    color: white;
}}

QPushButton[nav="true"]:checked {{
    background-color: {WII_GREEN};
}}

/* Поля ввода */
QLineEdit {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_GRAY};
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 14pt;
}}

QLineEdit:focus {{
    border-color: {WII_BLUE};
}}

/* Списки */
QListWidget {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_GRAY};
    border-radius: 12px;
    padding: 8px;
    font-size: 13pt;
}}

QListWidget::item {{
    background-color: {WII_WHITE};
    border: 1px solid {WII_GRAY};
    border-radius: 12px;
    padding: 10px;
    margin: 4px;
}}

QListWidget::item:selected {{
    background-color: {WII_LIGHT_BLUE};
    color: {WII_DARK_GRAY};
}}

/* Группы */
QGroupBox {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_BLUE};
    border-radius: 16px;
    padding: 16px;
    font-size: 14pt;
    font-weight: bold;
    color: {WII_DARK_GRAY};
    margin-top: 16px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 6px 12px;
    background-color: {WII_BLUE};
    color: white;
    border-radius: 10px;
}}

/* Прогресс-бар */
QProgressBar {{
    background-color: {WII_GRAY};
    border: none;
    border-radius: 12px;
    text-align: center;
    font-size: 14pt;
    min-height: 32px;
}}

QProgressBar::chunk {{
    background-color: {WII_GREEN};
    border-radius: 12px;
}}

/* Текстовые области */
QTextEdit {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_GRAY};
    border-radius: 12px;
    padding: 10px;
    font-size: 14pt;
}}

/* Прокрутка */
QScrollArea {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_GRAY};
    border-radius: 12px;
}}

/* Статус-бар */
QStatusBar {{
    background-color: {WII_BLUE};
    color: white;
    border: none;
    padding: 6px;
    font-size: 12pt;
}}

/* Меню */
QMenuBar {{
    background-color: {WII_BLUE};
    color: white;
    border: none;
    padding: 4px;
    font-size: 12pt;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 8px 16px;
    border-radius: 12px;
}}

QMenuBar::item:selected {{
    background-color: {WII_LIGHT_BLUE};
    color: {WII_DARK_GRAY};
}}

QMenu {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_BLUE};
    border-radius: 12px;
    padding: 8px;
}}

QMenu::item {{
    background-color: transparent;
    padding: 8px 20px;
    border-radius: 12px;
}}

QMenu::item:selected {{
    background-color: {WII_LIGHT_BLUE};
}}

/* Заголовок приложения */
QLabel[headerTitle="true"] {{
    background-color: {WII_BLUE};
    color: white;
    border-radius: 24px;
    padding: 20px;
    font-size: 24pt;
    font-weight: bold;
    min-height: 80px;
}}

/* Карточки игр */
QWidget[gameCard="true"] {{
    background-color: {WII_WHITE};
    border: 2px solid {WII_GRAY};
    border-radius: 20px;
    padding: 20px;
}}

QWidget[gameCard="true"]:hover {{
    border-color: {WII_ORANGE};
    background-color: {WII_LIGHT_BLUE};
}}
"""

@dataclass
class DownloadQueueItem:
    """Элемент очереди загрузки"""
    game: WiiGame
    download_url: str
    filename: str
    priority: int = 0
    
class DownloadQueue:
    """Менеджер очереди загрузок"""
    
    def __init__(self):
        self.queue = Queue()
        self.current_download = None
        self.is_downloading = False
        self.download_thread = None
        
    def add_download(self, item: DownloadQueueItem):
        """Добавить загрузку в очередь"""
        self.queue.put(item)
        
    def get_queue_size(self) -> int:
        """Получить размер очереди"""
        return self.queue.qsize()
        
    def is_empty(self) -> bool:
        """Проверить, пуста ли очередь"""
        return self.queue.empty()
        
    def get_next_download(self) -> Optional[DownloadQueueItem]:
        """Получить следующую загрузку из очереди"""
        try:
            return self.queue.get_nowait()
        except Empty:
            return None

class GameCard(QWidget):
    """Полная карточка игры с детальной информацией"""

    def __init__(self, game: WiiGame, parent=None):
        super().__init__(parent)
        self.game = game
        self.setProperty("gameCard", True)
        self.setFixedSize(460, 700)
        self.setup_ui()
        self.load_game_details()
        
    def setup_ui(self):
        """Настройка интерфейса карточки"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Заголовок с названием игры
        self.title_label = QLabel(self.game.title)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                background-color: {WII_WHITE};
                border-radius: 8px;
                padding: 10px;
                border: 2px solid {WII_BLUE};
            }}
        """)
        layout.addWidget(self.title_label)
        
        # Создаем вкладки для информации
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: {WII_WHITE};
            }}
            QTabBar::tab {{
                background-color: {WII_LIGHT_GRAY};
                color: {WII_BLUE};
                padding: 6px 12px;
                margin-right: 2px;
                border: 2px solid {WII_GRAY};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: {WII_WHITE};
                border-color: {WII_BLUE};
                color: {WII_BLUE};
            }}
            QTabBar::tab:hover {{
                background-color: {WII_LIGHT_BLUE};
            }}
        """)
        
        # Вкладка "Общая информация"
        general_tab = QWidget()
        general_layout = QFormLayout()
        general_layout.setSpacing(8)
        general_layout.setContentsMargins(12, 12, 12, 12)
        
        # Создаем поля для основной информации
        self.region_label = QLabel(self.game.region or "Не указано")
        self.version_label = QLabel(self.game.version or "Не указано")
        self.languages_label = QLabel(self.game.languages or "Не указано")
        self.rating_label = QLabel(self.game.rating or "Не указано")
        self.serial_label = QLabel(self.game.serial or "Не указано")
        self.players_label = QLabel(self.game.players or "Не указано")
        self.year_label = QLabel(self.game.year or "Не указано")
        self.file_size_label = QLabel(self.game.file_size or "Не указано")
        
        # Применяем стили к полям
        for label in [self.region_label, self.version_label, self.languages_label, 
                     self.rating_label, self.serial_label, self.players_label, 
                     self.year_label, self.file_size_label]:
            label.setStyleSheet(f"""
                QLabel {{
                    background-color: {WII_LIGHT_GRAY};
                    border: 1px solid {WII_GRAY};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }}
            """)
        
        general_layout.addRow("Регион:", self.region_label)
        general_layout.addRow("Версия:", self.version_label)
        general_layout.addRow("Языки:", self.languages_label)
        general_layout.addRow("Рейтинг:", self.rating_label)
        general_layout.addRow("Серийный номер:", self.serial_label)
        general_layout.addRow("Игроки:", self.players_label)
        general_layout.addRow("Год:", self.year_label)
        general_layout.addRow("Размер файла:", self.file_size_label)
        
        general_tab.setLayout(general_layout)
        tabs.addTab(general_tab, "Общая информация")
        
        # Вкладка "Оценки"
        ratings_tab = QWidget()
        ratings_layout = QFormLayout()
        ratings_layout.setSpacing(8)
        ratings_layout.setContentsMargins(12, 12, 12, 12)
        
        self.graphics_label = QLabel(self.game.graphics or "Не указано")
        self.sound_label = QLabel(self.game.sound or "Не указано")
        self.gameplay_label = QLabel(self.game.gameplay or "Не указано")
        self.overall_label = QLabel(self.game.overall or "Не указано")
        self.crc_label = QLabel(self.game.crc or "Не указано")
        self.verified_label = QLabel(self.game.verified or "Не указано")
        
        # Применяем стили к полям оценок
        for label in [self.graphics_label, self.sound_label, self.gameplay_label, 
                     self.overall_label, self.crc_label, self.verified_label]:
            label.setStyleSheet(f"""
                QLabel {{
                    background-color: {WII_LIGHT_GRAY};
                    border: 1px solid {WII_GRAY};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }}
            """)
        
        ratings_layout.addRow("Графика:", self.graphics_label)
        ratings_layout.addRow("Звук:", self.sound_label)
        ratings_layout.addRow("Геймплей:", self.gameplay_label)
        ratings_layout.addRow("Общий рейтинг:", self.overall_label)
        ratings_layout.addRow("CRC:", self.crc_label)
        ratings_layout.addRow("Проверено:", self.verified_label)
        
        ratings_tab.setLayout(ratings_layout)
        tabs.addTab(ratings_tab, "Оценки")
        
        # Вкладка "Изображения"
        images_tab = QWidget()
        images_layout = QHBoxLayout()
        images_layout.setSpacing(12)
        images_layout.setContentsMargins(12, 12, 12, 12)
        
        # Обложка
        box_group = QGroupBox("Обложка")
        box_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {WII_BLUE};
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: {WII_WHITE};
            }}
        """)
        box_layout = QVBoxLayout(box_group)
        self.box_image = QLabel()
        self.box_image.setAlignment(Qt.AlignCenter)
        self.box_image.setFixedSize(180, 250)
        self.box_image.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: {WII_LIGHT_GRAY};
                color: {WII_DARK_GRAY};
                font-size: 10pt;
            }}
        """)
        self.box_image.setText("Загрузка...")
        box_layout.addWidget(self.box_image)
        
        # Диск
        disc_group = QGroupBox("Диск")
        disc_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {WII_BLUE};
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: {WII_WHITE};
            }}
        """)
        disc_layout = QVBoxLayout(disc_group)
        self.disc_image = QLabel()
        self.disc_image.setAlignment(Qt.AlignCenter)
        self.disc_image.setFixedSize(150, 150)
        self.disc_image.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: {WII_LIGHT_GRAY};
                color: {WII_DARK_GRAY};
                font-size: 10pt;
            }}
        """)
        self.disc_image.setText("Загрузка...")
        disc_layout.addWidget(self.disc_image)
        
        images_layout.addWidget(box_group)
        images_layout.addWidget(disc_group)
        images_tab.setLayout(images_layout)
        tabs.addTab(images_tab, "Изображения")
        
        layout.addWidget(tabs)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("📥 Скачать")
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_GREEN};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid {WII_GREEN};
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #218838;
                border-color: #1e7e34;
            }}
            QPushButton:pressed {{
                background-color: #1e7e34;
            }}
        """)
        
        self.open_url_btn = QPushButton("🌐 Открыть")
        self.open_url_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_BLUE};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid {WII_BLUE};
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #3976db;
                border-color: #2d5aa0;
            }}
            QPushButton:pressed {{
                background-color: #2d5aa0;
            }}
        """)
        
        buttons_layout.addWidget(self.download_btn)
        buttons_layout.addWidget(self.open_url_btn)
        layout.addLayout(buttons_layout)
        
        # Подключаем сигналы
        self.open_url_btn.clicked.connect(self.open_game_url)
        
    def load_game_details(self):
        """Загрузка детальной информации об игре"""
        # Загружаем изображения
        self.load_images()
        
        # Проверяем доступность URL
        if not self.game.detail_url:
            self.open_url_btn.setEnabled(False)

    def update_game(self, game: WiiGame):
        """Обновить карточку новыми данными"""
        self.game = game
        self.title_label.setText(game.title)
        self.region_label.setText(game.region or "Не указано")
        self.version_label.setText(game.version or "Не указано")
        self.languages_label.setText(game.languages or "Не указано")
        self.rating_label.setText(game.rating or "Не указано")
        self.serial_label.setText(game.serial or "Не указано")
        self.players_label.setText(game.players or "Не указано")
        self.year_label.setText(game.year or "Не указано")
        self.file_size_label.setText(game.file_size or "Не указано")

        self.graphics_label.setText(game.graphics or "Не указано")
        self.sound_label.setText(game.sound or "Не указано")
        self.gameplay_label.setText(game.gameplay or "Не указано")
        self.overall_label.setText(game.overall or "Не указано")
        self.crc_label.setText(game.crc or "Не указано")
        self.verified_label.setText(game.verified or "Не указано")

        self.load_images()
        
    def load_images(self):
        """Загрузка изображений игры"""
        if self.game.box_art:
            self.load_image_from_url(self.game.box_art, self.box_image)
        else:
            self.box_image.setText("Нет изображения")
            
        if self.game.disc_art:
            self.load_image_from_url(self.game.disc_art, self.disc_image)
        else:
            self.disc_image.setText("Нет изображения")
            
    def load_image_from_url(self, url: str, label: QLabel):
        """Загрузка изображения по URL (как в базовой версии)"""
        try:
            # Исправляем URL если необходимо
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = 'https://vimm.net' + url
            
            if url.startswith('data:'):
                # Обработка base64 изображений
                header, data = url.split(',', 1)
                image_data = base64.b64decode(data)
                
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    label.setPixmap(scaled_pixmap)
                else:
                    label.setText("Ошибка загрузки")
            else:
                # Загрузка обычного изображения
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://vimm.net/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        label.setPixmap(scaled_pixmap)
                    else:
                        label.setText("Ошибка загрузки")
                else:
                    label.setText("Изображение недоступно")
                    
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            label.setText(f"Ошибка: {str(e)[:20]}...")
            
    def on_image_loaded(self, pixmap: QPixmap, label: QLabel):
        """Обработка загруженного изображения"""
        if not pixmap.isNull():
            label.setPixmap(pixmap)
        else:
            label.setText("Ошибка загрузки")
            
    def open_game_url(self):
        """Открытие URL игры в браузере"""
        if self.game.detail_url:
            QDesktopServices.openUrl(self.game.detail_url)
        else:
            QMessageBox.information(self, "Информация", "URL игры не найден")

class WiiUnifiedManager(QMainWindow):
    """Главное окно объединенного менеджера"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎮 Wii Unified Manager - Менеджер игр Nintendo Wii")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon())  # Можно добавить иконку
        
        # Инициализация компонентов
        self.parser = WiiGameParser()
        self.database = WiiGameDatabase()
        self.downloader = WiiGameSeleniumDownloader()
        self.download_queue = DownloadQueue()
        
        # Загруженные игры
        self.online_games = []
        self.downloaded_games = []
        self.flash_games = []
        self.current_drive = None
        self.current_section = "search"  # "search" или "manager"
        
        # Таймеры
        self.download_timer = QTimer()
        self.download_timer.timeout.connect(self.process_download_queue)
        self.download_timer.start(2000)  # Проверяем очередь каждые 2 секунды
        
        self.setup_ui()
        self.load_saved_games()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        self.setStyleSheet(WII_STYLE)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный макет
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Заголовок приложения
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Навигация разделов
        navigation = self.create_navigation()
        main_layout.addWidget(navigation)
        
        # Основное содержимое - единый интерфейс
        self.main_content = self.create_unified_interface()
        main_layout.addWidget(self.main_content)
        
        # Статус-бар
        self.setup_status_bar()
        
        # Меню
        self.setup_menu()
        
    def create_header(self) -> QWidget:
        """Создание заголовка приложения"""
        header = QLabel("🎮 Wii Unified Manager")
        header.setProperty("headerTitle", True)
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(80)
        return header
        
    def create_navigation(self) -> QWidget:
        """Создание навигации разделов"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setSpacing(20)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Кнопка поиска
        self.search_btn = QPushButton("🔍 Поиск")
        self.search_btn.setProperty("nav", True)
        self.search_btn.setCheckable(True)
        self.search_btn.setChecked(True)
        self.search_btn.clicked.connect(self.show_search_section)
        
        # Кнопка менеджера игр
        self.manager_btn = QPushButton("💾 Менеджер игр")
        self.manager_btn.setProperty("nav", True)
        self.manager_btn.setCheckable(True)
        self.manager_btn.clicked.connect(self.show_manager_section)
        
        # Группа кнопок
        self.nav_group = QButtonGroup()
        self.nav_group.addButton(self.search_btn)
        self.nav_group.addButton(self.manager_btn)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.search_btn)
        nav_layout.addWidget(self.manager_btn)
        nav_layout.addStretch()
        
        return nav_widget
        
    def create_unified_interface(self) -> QWidget:
        """Создание единого интерфейса с поиском слева и карточкой справа"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(16)
        
        # Панель поиска сверху
        search_panel = QWidget()
        search_layout = QHBoxLayout(search_panel)
        search_layout.setSpacing(12)
        
        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название игры для поиска...")
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 12pt;
                padding: 8px 16px;
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
            }}
            QLineEdit:focus {{
                border-color: {WII_BLUE};
            }}
        """)
        self.search_input.returnPressed.connect(self.perform_search)
        
        # Кнопка поиска
        self.search_action_btn = QPushButton("🔍 Найти")
        self.search_action_btn.setMinimumHeight(40)
        self.search_action_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12pt;
                font-weight: bold;
                padding: 8px 20px;
                background-color: {WII_BLUE};
                color: white;
                border: 2px solid {WII_BLUE};
                border-radius: 8px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: #3976db;
                border-color: #2d5aa0;
            }}
        """)
        self.search_action_btn.clicked.connect(self.perform_search)
        
        # Кнопка управления флешкой
        self.manage_flash_btn = QPushButton("💾 Управление флешкой")
        self.manage_flash_btn.setMinimumHeight(40)
        self.manage_flash_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12pt;
                font-weight: bold;
                padding: 8px 20px;
                background-color: {WII_GREEN};
                color: white;
                border: 2px solid {WII_GREEN};
                border-radius: 8px;
                min-width: 150px;
            }}
            QPushButton:hover {{
                background-color: #218838;
                border-color: #1e7e34;
            }}
        """)
        self.manage_flash_btn.clicked.connect(self.toggle_flash_panel)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_action_btn)
        search_layout.addWidget(self.manage_flash_btn)
        
        layout.addWidget(search_panel)
        
        # Основной контент - разделитель
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setSizes([500, 700])
        
        # Левая панель - поиск и списки игр
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # Правая панель - карточка игры
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        layout.addWidget(main_splitter)
        
        return main_widget
        
    def create_left_panel(self) -> QWidget:
        """Создание левой панели с поиском и списками"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # Вкладки для разных типов игр
        self.games_tabs = QTabWidget()
        self.games_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: white;
            }}
            QTabBar::tab {{
                background-color: {WII_LIGHT_GRAY};
                border: 2px solid {WII_GRAY};
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 8px 16px;
                font-size: 11pt;
                font-weight: bold;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                background-color: {WII_BLUE};
                color: white;
            }}
        """)
        
        # Вкладка поиска
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setSpacing(8)
        
        # Список найденных игр
        self.online_games_list = QListWidget()
        self.online_games_list.setMinimumHeight(400)
        self.online_games_list.itemClicked.connect(self.on_game_selected)
        self.online_games_list.setStyleSheet(f"""
            QListWidget::item {{
                padding: 12px 8px;
                border: 1px solid {WII_GRAY};
                border-radius: 6px;
                margin: 2px;
                background-color: white;
            }}
            QListWidget::item:selected {{
                background-color: {WII_BLUE};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {WII_LIGHT_BLUE};
            }}
        """)
        search_layout.addWidget(self.online_games_list)
        
        # Статистика поиска
        self.search_stats = QLabel("Игр найдено: 0")
        self.search_stats.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 4px;
            }}
        """)
        search_layout.addWidget(self.search_stats)
        
        # Вкладка скачанных игр
        downloaded_tab = QWidget()
        downloaded_layout = QVBoxLayout(downloaded_tab)
        downloaded_layout.setSpacing(8)

        # Очередь загрузок
        queue_label = QLabel("Очередь загрузок")
        queue_label.setAlignment(Qt.AlignCenter)
        downloaded_layout.addWidget(queue_label)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        downloaded_layout.addWidget(self.queue_list)
        
        # Список скачанных игр
        self.downloaded_games_list = QListWidget()
        self.downloaded_games_list.setMinimumHeight(400)
        self.downloaded_games_list.itemClicked.connect(self.on_game_selected)
        self.downloaded_games_list.setStyleSheet(f"""
            QListWidget::item {{
                padding: 12px 8px;
                border: 1px solid {WII_GRAY};
                border-radius: 6px;
                margin: 2px;
                background-color: white;
            }}
            QListWidget::item:selected {{
                background-color: {WII_BLUE};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {WII_LIGHT_BLUE};
            }}
        """)
        downloaded_layout.addWidget(self.downloaded_games_list)
        
        # Кнопки управления скачанными играми
        downloaded_buttons = QHBoxLayout()
        
        self.install_to_flash_btn = QPushButton("💾 На флешку")
        self.install_to_flash_btn.clicked.connect(self.install_selected_to_flash)
        self.install_to_flash_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_GREEN};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
        """)
        
        self.delete_downloaded_btn = QPushButton("🗑️ Удалить")
        self.delete_downloaded_btn.clicked.connect(self.delete_downloaded_game)
        self.delete_downloaded_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_RED};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        
        downloaded_buttons.addWidget(self.install_to_flash_btn)
        downloaded_buttons.addWidget(self.delete_downloaded_btn)
        downloaded_layout.addLayout(downloaded_buttons)
        
        # Статистика скачанных игр
        self.downloaded_stats = QLabel("Скачано: 0")
        self.downloaded_stats.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 4px;
            }}
        """)
        downloaded_layout.addWidget(self.downloaded_stats)
        
        # Добавляем вкладки
        self.games_tabs.addTab(search_tab, "🔍 Поиск")
        self.games_tabs.addTab(downloaded_tab, "📥 Скачанные")
        
        layout.addWidget(self.games_tabs)
        
        # Панель управления флешкой (скрыта по умолчанию)
        self.flash_panel = self.create_flash_panel()
        self.flash_panel.setVisible(False)
        layout.addWidget(self.flash_panel)
        
        return panel
        
    def create_flash_panel(self) -> QWidget:
        """Создание панели управления флешкой"""
        panel = QGroupBox("💾 Управление флешкой")
        panel.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12pt;
                color: {WII_BLUE};
                border: 2px solid {WII_BLUE};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: {WII_WHITE};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # Выбор диска
        drive_section = QWidget()
        drive_layout = QHBoxLayout(drive_section)
        drive_layout.setSpacing(8)
        
        drive_label = QLabel("Диск:")
        drive_label.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {WII_DARK_GRAY};")
        
        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumHeight(30)
        self.drive_combo.currentTextChanged.connect(self.on_drive_changed)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.clicked.connect(self.refresh_drives)
        
        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.drive_combo)
        drive_layout.addWidget(refresh_btn)
        
        layout.addWidget(drive_section)
        
        # Список игр на флешке
        self.flash_games_list = QListWidget()
        self.flash_games_list.setMaximumHeight(200)
        self.flash_games_list.itemClicked.connect(self.on_game_selected)
        self.flash_games_list.setStyleSheet(f"""
            QListWidget::item {{
                padding: 8px;
                border: 1px solid {WII_GRAY};
                border-radius: 4px;
                margin: 1px;
                background-color: white;
            }}
            QListWidget::item:selected {{
                background-color: {WII_GREEN};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {WII_LIGHT_BLUE};
            }}
        """)
        layout.addWidget(self.flash_games_list)
        
        # Кнопки управления флешкой
        flash_buttons = QHBoxLayout()
        
        self.add_external_btn = QPushButton("📁 Добавить внешние")
        self.add_external_btn.clicked.connect(self.add_external_games)
        
        self.remove_from_flash_btn = QPushButton("❌ Удалить")
        self.remove_from_flash_btn.clicked.connect(self.remove_from_flash)
        
        flash_buttons.addWidget(self.add_external_btn)
        flash_buttons.addWidget(self.remove_from_flash_btn)
        
        layout.addLayout(flash_buttons)
        
        # Статистика флешки
        self.flash_stats = QLabel("Игр на флешке: 0")
        self.flash_stats.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.flash_stats)
        
        return panel
        
    def create_right_panel(self) -> QWidget:
        """Создание правой панели с карточкой игры"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        
        # Заголовок
        header = QLabel("🎮 Информация об игре")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 16pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 12px;
                background-color: {WII_WHITE};
                border: 2px solid {WII_BLUE};
                border-radius: 8px;
                text-align: center;
            }}
        """)
        layout.addWidget(header)
        
        # Скролл-область для карточки
        self.card_scroll = QScrollArea()
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: white;
            }}
        """)
        
        # Виджет для карточки
        self.card_widget = QWidget()
        self.card_layout = QVBoxLayout(self.card_widget)
        self.card_layout.setAlignment(Qt.AlignTop)
        
        # Заглушка по умолчанию
        self.show_placeholder()
        
        self.card_scroll.setWidget(self.card_widget)
        layout.addWidget(self.card_scroll)
        
        # Панель загрузки (скрыта по умолчанию)
        self.download_panel = self.create_download_panel()
        self.download_panel.setVisible(False)
        layout.addWidget(self.download_panel)
        
        return panel
        
    def create_download_panel(self) -> QWidget:
        """Создание панели загрузки"""
        panel = QGroupBox("📥 Загрузки")
        panel.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12pt;
                color: {WII_BLUE};
                border: 2px solid {WII_BLUE};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: {WII_WHITE};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        
        # Текущая загрузка
        self.current_download_label = QLabel("Нет активных загрузок")
        self.current_download_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
            }}
        """)
        layout.addWidget(self.current_download_label)
        
        # Прогресс-бар
        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        self.download_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {WII_BLUE};
                border-radius: 6px;
                text-align: center;
                font-size: 11pt;
                font-weight: bold;
                min-height: 24px;
                background-color: {WII_LIGHT_GRAY};
            }}
            QProgressBar::chunk {{
                background-color: {WII_GREEN};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.download_progress)
        
        # Информация о загрузке
        self.download_info = QLabel("")
        self.download_info.setVisible(False)
        self.download_info.setStyleSheet(f"""
            QLabel {{
                font-size: 10pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.download_info)
        
        # Кнопка отмены
        self.cancel_download_btn = QPushButton("❌ Отменить")
        self.cancel_download_btn.setVisible(False)
        self.cancel_download_btn.clicked.connect(self.cancel_download)
        self.cancel_download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_RED};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
        """)
        layout.addWidget(self.cancel_download_btn)
        
        return panel
        
    def show_placeholder(self):
        """Показать заглушку в карточке"""
        # Очищаем предыдущую карточку
        for i in reversed(range(self.card_layout.count())):
            child = self.card_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
        
        # Создаем заглушку
        placeholder = QLabel("Выберите игру для просмотра подробной информации")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                color: {WII_DARK_GRAY};
                padding: 60px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 12px;
                border: 2px dashed {WII_GRAY};
            }}
        """)
        self.card_layout.addWidget(placeholder)
        
    def toggle_flash_panel(self):
        """Переключить видимость панели управления флешкой"""
        self.flash_panel.setVisible(not self.flash_panel.isVisible())
        if self.flash_panel.isVisible():
            self.manage_flash_btn.setText("💾 Скрыть управление")
            self.refresh_drives()
        else:
            self.manage_flash_btn.setText("💾 Управление флешкой")
        
    def create_search_page(self) -> QWidget:
        """Создание страницы поиска"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Панель поиска
        search_panel = QWidget()
        search_layout = QHBoxLayout(search_panel)
        search_layout.setSpacing(12)
        
        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название игры для поиска...")
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 12pt;
                padding: 8px 16px;
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
            }}
            QLineEdit:focus {{
                border-color: {WII_BLUE};
            }}
        """)
        self.search_input.returnPressed.connect(self.perform_search)
        
        # Кнопка поиска
        self.search_action_btn = QPushButton("🔍 Найти")
        self.search_action_btn.setMinimumHeight(40)
        self.search_action_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12pt;
                font-weight: bold;
                padding: 8px 20px;
                background-color: {WII_BLUE};
                color: white;
                border: 2px solid {WII_BLUE};
                border-radius: 8px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: #3976db;
                border-color: #2d5aa0;
            }}
        """)
        self.search_action_btn.clicked.connect(self.perform_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_action_btn)
        
        layout.addWidget(search_panel)
        
        # Основной контент
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setSizes([400, 600])
        
        # Левая панель - список игр
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # Заголовок списка
        games_header = QLabel("Найденные игры")
        games_header.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 8px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 6px;
            }}
        """)
        left_layout.addWidget(games_header)
        
        # Список игр
        self.online_games_list = QListWidget()
        self.online_games_list.setMinimumWidth(350)
        self.online_games_list.itemClicked.connect(self.on_online_game_selected)
        left_layout.addWidget(self.online_games_list)
        
        # Статистика поиска
        self.search_stats = QLabel("Игр найдено: 0")
        self.search_stats.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
            }}
        """)
        left_layout.addWidget(self.search_stats)
        
        content_splitter.addWidget(left_panel)
        
        # Правая панель - карточка игры
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        
        # Заголовок карточки
        card_header = QLabel("Информация об игре")
        card_header.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 8px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 6px;
            }}
        """)
        right_layout.addWidget(card_header)
        
        # Скролл-область для карточки
        self.search_card_scroll = QScrollArea()
        self.search_card_scroll.setWidgetResizable(True)
        self.search_card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Виджет для карточки
        self.search_card_widget = QWidget()
        self.search_card_layout = QVBoxLayout(self.search_card_widget)
        
        # Заглушка
        placeholder = QLabel("Выберите игру для просмотра подробной информации")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"""
            QLabel {{
                font-size: 12pt;
                color: {WII_DARK_GRAY};
                padding: 40px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 8px;
                border: 2px dashed {WII_GRAY};
            }}
        """)
        self.search_card_layout.addWidget(placeholder)
        
        self.search_card_scroll.setWidget(self.search_card_widget)
        right_layout.addWidget(self.search_card_scroll)
        
        content_splitter.addWidget(right_panel)
        layout.addWidget(content_splitter)
        
        return page
        
    def create_manager_page(self) -> QWidget:
        """Создание страницы менеджера игр"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Панель управления
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        control_layout.setSpacing(12)
        
        # Выбор диска
        drive_label = QLabel("Флешка:")
        drive_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {WII_BLUE};")
        
        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(200)
        self.drive_combo.setMinimumHeight(35)
        self.drive_combo.currentTextChanged.connect(self.on_drive_changed)
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.setMinimumHeight(35)
        refresh_btn.clicked.connect(self.refresh_drives)
        
        # Поиск по играм
        search_label = QLabel("Поиск игр:")
        search_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {WII_BLUE};")
        
        self.manager_search_input = QLineEdit()
        self.manager_search_input.setPlaceholderText("Поиск среди скачанных игр...")
        self.manager_search_input.setMinimumHeight(35)
        self.manager_search_input.textChanged.connect(self.filter_manager_games)
        
        control_layout.addWidget(drive_label)
        control_layout.addWidget(self.drive_combo)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()
        control_layout.addWidget(search_label)
        control_layout.addWidget(self.manager_search_input)
        
        layout.addWidget(control_panel)
        
        # Основной контент
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setSizes([400, 600])
        
        # Левая панель - список игр
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # Вкладки для разных типов игр
        self.manager_tabs = QTabWidget()
        self.manager_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid {WII_GRAY};
                border-radius: 8px;
                background-color: white;
            }}
            QTabBar::tab {{
                background-color: {WII_LIGHT_GRAY};
                border: 2px solid {WII_GRAY};
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 8px 16px;
                font-size: 11pt;
                font-weight: bold;
                min-width: 100px;
            }}
            QTabBar::tab:selected {{
                background-color: {WII_BLUE};
                color: white;
            }}
        """)
        
        # Вкладка скачанных игр
        downloaded_tab = QWidget()
        downloaded_layout = QVBoxLayout(downloaded_tab)
        
        downloaded_header = QLabel("Скачанные игры")
        downloaded_header.setStyleSheet(f"""
            QLabel {{
                font-size: 12pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 8px;
            }}
        """)
        downloaded_layout.addWidget(downloaded_header)

        queue_label = QLabel("Очередь загрузок")
        queue_label.setAlignment(Qt.AlignCenter)
        downloaded_layout.addWidget(queue_label)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        downloaded_layout.addWidget(self.queue_list)
        
        self.downloaded_games_list = QListWidget()
        self.downloaded_games_list.itemClicked.connect(self.on_downloaded_game_selected)
        downloaded_layout.addWidget(self.downloaded_games_list)
        
        # Кнопки управления скачанными играми
        downloaded_buttons = QWidget()
        downloaded_buttons_layout = QHBoxLayout(downloaded_buttons)
        
        self.install_to_flash_btn = QPushButton("💾 Установить на флешку")
        self.install_to_flash_btn.clicked.connect(self.install_selected_to_flash)
        
        self.delete_downloaded_btn = QPushButton("🗑️ Удалить файл")
        self.delete_downloaded_btn.clicked.connect(self.delete_downloaded_game)
        
        downloaded_buttons_layout.addWidget(self.install_to_flash_btn)
        downloaded_buttons_layout.addWidget(self.delete_downloaded_btn)
        
        downloaded_layout.addWidget(downloaded_buttons)
        
        # Вкладка игр на флешке
        flash_tab = QWidget()
        flash_layout = QVBoxLayout(flash_tab)
        
        flash_header = QLabel("Игры на флешке")
        flash_header.setStyleSheet(f"""
            QLabel {{
                font-size: 12pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 8px;
            }}
        """)
        flash_layout.addWidget(flash_header)
        
        self.flash_games_list = QListWidget()
        self.flash_games_list.itemClicked.connect(self.on_flash_game_selected)
        flash_layout.addWidget(self.flash_games_list)
        
        # Кнопки управления играми на флешке
        flash_buttons = QWidget()
        flash_buttons_layout = QHBoxLayout(flash_buttons)
        
        self.add_external_btn = QPushButton("📁 Добавить внешние игры")
        self.add_external_btn.clicked.connect(self.add_external_games)
        
        self.remove_from_flash_btn = QPushButton("❌ Удалить с флешки")
        self.remove_from_flash_btn.clicked.connect(self.remove_from_flash)
        
        flash_buttons_layout.addWidget(self.add_external_btn)
        flash_buttons_layout.addWidget(self.remove_from_flash_btn)
        
        flash_layout.addWidget(flash_buttons)
        
        # Добавляем вкладки
        self.manager_tabs.addTab(downloaded_tab, "📥 Скачанные")
        self.manager_tabs.addTab(flash_tab, "💾 На флешке")
        
        left_layout.addWidget(self.manager_tabs)
        
        # Статистика
        self.manager_stats = QLabel("Статистика загружается...")
        self.manager_stats.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                color: {WII_DARK_GRAY};
                padding: 4px;
            }}
        """)
        left_layout.addWidget(self.manager_stats)
        
        content_splitter.addWidget(left_panel)
        
        # Правая панель - карточка игры
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        
        # Заголовок карточки
        manager_card_header = QLabel("Информация об игре")
        manager_card_header.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                padding: 8px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 6px;
            }}
        """)
        right_layout.addWidget(manager_card_header)
        
        # Скролл-область для карточки
        self.manager_card_scroll = QScrollArea()
        self.manager_card_scroll.setWidgetResizable(True)
        self.manager_card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Виджет для карточки
        self.manager_card_widget = QWidget()
        self.manager_card_layout = QVBoxLayout(self.manager_card_widget)
        
        # Заглушка
        manager_placeholder = QLabel("Выберите игру для просмотра подробной информации")
        manager_placeholder.setAlignment(Qt.AlignCenter)
        manager_placeholder.setStyleSheet(f"""
            QLabel {{
                font-size: 12pt;
                color: {WII_DARK_GRAY};
                padding: 40px;
                background-color: {WII_LIGHT_GRAY};
                border-radius: 8px;
                border: 2px dashed {WII_GRAY};
            }}
        """)
        self.manager_card_layout.addWidget(manager_placeholder)
        
        self.manager_card_scroll.setWidget(self.manager_card_widget)
        right_layout.addWidget(self.manager_card_scroll)
        
        # Индикатор прогресса операций
        self.manager_progress = QProgressBar()
        self.manager_progress.setVisible(False)
        self.manager_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {WII_BLUE};
                border-radius: 6px;
                text-align: center;
                font-size: 11pt;
                font-weight: bold;
                min-height: 28px;
                background-color: {WII_LIGHT_GRAY};
            }}
            QProgressBar::chunk {{
                background-color: {WII_GREEN};
                border-radius: 4px;
            }}
        """)
        right_layout.addWidget(self.manager_progress)
        
        content_splitter.addWidget(right_panel)
        layout.addWidget(content_splitter)
        
        return page
        
        
    def show_search_section(self):
        """Показать вкладку поиска"""
        self.games_tabs.setCurrentIndex(0)
        self.search_btn.setChecked(True)
        self.manager_btn.setChecked(False)
        self.status_label.setText("Раздел: Поиск игр")
        
    def show_manager_section(self):
        """Показать вкладку скачанных игр"""
        self.games_tabs.setCurrentIndex(1)
        self.manager_btn.setChecked(True)
        self.search_btn.setChecked(False)
        self.status_label.setText("Раздел: Скачанные игры")
        self.refresh_downloaded_games()
        
    def on_game_selected(self, item: QListWidgetItem):
        """Обработка выбора игры из любого списка"""
        data = item.data(Qt.UserRole)
        
        if isinstance(data, WiiGame):
            # Это игра из поиска
            self.show_game_card(data)
        elif isinstance(data, Path):
            # Это скачанная игра
            self.show_downloaded_game_card(data)
        elif hasattr(data, 'display_title'):
            # Это игра с флешки
            self.show_flash_game_card(data)
            
    def show_game_card(self, game: WiiGame):
        """Показать карточку игры из поиска"""
        # Очищаем предыдущую карточку
        for i in reversed(range(self.card_layout.count())):
            child = self.card_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
                
        # Создаем новую карточку
        card = GameCard(game)
        card.download_btn.clicked.connect(lambda: self.download_game(game))

        self.card_layout.addWidget(card)

        # Если информации мало, загружаем подробности в фоне
        if not game.serial and game.detail_url:
            self.status_label.setText("Загрузка информации об игре...")
            self.details_thread = GameDetailsThread(self.parser, game.detail_url)
            self.details_thread.details_loaded.connect(lambda g: self.on_details_loaded(g, card))
            self.details_thread.start()

        # Проверяем, есть ли игра в скачанных
        self.check_game_status(game, card)

    def on_details_loaded(self, details: WiiGame, card: GameCard):
        """Обновить карточку после загрузки деталей"""
        card.update_game(details)
        self.status_label.setText("Информация загружена")
        
    def check_game_status(self, game: WiiGame, card: GameCard):
        """Проверить статус игры (скачана/установлена)"""
        # Проверяем, скачана ли игра
        downloads_dir = Path("downloads")
        if downloads_dir.exists():
            game_files = list(downloads_dir.glob(f"*{game.title}*"))
            if game_files:
                # Игра скачана - изменяем кнопку
                card.download_btn.setText("✅ Скачана")
                card.download_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {WII_DARK_GRAY};
                        color: white;
                        font-size: 11pt;
                        font-weight: bold;
                        padding: 8px 16px;
                        border-radius: 6px;
                        border: 2px solid {WII_DARK_GRAY};
                        min-height: 32px;
                    }}
                """)
                card.download_btn.setEnabled(False)
                
        # Проверяем, установлена ли игра на флешке
        if self.current_drive and self.flash_games:
            for flash_game in self.flash_games:
                if game.title.lower() in flash_game.display_title.lower():
                    # Игра на флешке - добавляем индикатор
                    card.title_label.setText(f"💾 {game.title}")
                    break
                    
    def load_saved_games(self):
        """Загрузить сохраненные игры"""
        self.database.load_database()
        saved_games = self.database.games  # games уже список, не словарь
        if saved_games:
            self.online_games = saved_games
            self.display_online_games(saved_games)
            self.status_label.setText(f"Загружено сохраненных игр: {len(saved_games)}")
            
    def display_online_games(self, games: List[WiiGame]):
        """Отображение списка найденных игр"""
        self.online_games_list.clear()
        
        for game in games:
            item = QListWidgetItem()
            
            # Проверяем статус игры
            status_icon = "🎮"
            if self.is_game_downloaded(game):
                status_icon = "✅"
            elif self.is_game_on_flash(game):
                status_icon = "💾"
            
            item.setText(f"{status_icon} {game.title}\n🌍 {game.region} • ⭐ {game.rating}")
            item.setData(Qt.UserRole, game)
            
            # Стилизация элементов списка
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            item.setFont(font)
            
            self.online_games_list.addItem(item)
            
        self.search_stats.setText(f"Игр найдено: {len(games)}")
        
    def is_game_downloaded(self, game: WiiGame) -> bool:
        """Проверить, скачана ли игра"""
        downloads_dir = Path("downloads")
        if downloads_dir.exists():
            game_files = list(downloads_dir.glob(f"*{game.title}*"))
            return len(game_files) > 0
        return False
        
    def is_game_on_flash(self, game: WiiGame) -> bool:
        """Проверить, установлена ли игра на флешке"""
        if self.current_drive and self.flash_games:
            for flash_game in self.flash_games:
                if game.title.lower() in flash_game.display_title.lower():
                    return True
        return False
        
    def on_online_game_selected(self, item: QListWidgetItem):
        """Обработка выбора игры в поиске"""
        game = item.data(Qt.UserRole)
        if game:
            self.show_online_game_card(game)
            
    def show_online_game_card(self, game: WiiGame):
        """Показать карточку найденной игры"""
        # Очищаем предыдущую карточку
        for i in reversed(range(self.search_card_layout.count())):
            child = self.search_card_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
                
        # Создаем новую карточку
        card = GameCard(game)
        card.download_btn.clicked.connect(lambda: self.download_game(game))
        
        self.search_card_layout.addWidget(card)
        self.search_card_layout.addStretch()
        
    def download_game(self, game: WiiGame):
        """Добавить игру в очередь загрузки"""
        if not game.detail_url:
            QMessageBox.warning(self, "Ошибка", "У игры нет ссылки для загрузки")
            return
            
        # Создаем элемент очереди
        filename = f"{game.title} [{game.region}].wbfs"
        item = DownloadQueueItem(game, game.detail_url, filename)
        
        # Добавляем в очередь
        self.download_queue.add_download(item)

        queue_item = QListWidgetItem(f"⏳ {game.title}")
        queue_item.setData(Qt.UserRole, item)
        self.queue_list.addItem(queue_item)

        self.update_download_indicator()
        
        QMessageBox.information(self, "Загрузка", f"Игра '{game.title}' добавлена в очередь загрузки")
        
    def process_download_queue(self):
        """Обработка очереди загрузок"""
        if not self.download_queue.is_downloading and not self.download_queue.is_empty():
            item = self.download_queue.get_next_download()
            if item:
                if self.queue_list.count() > 0:
                    self.queue_list.takeItem(0)
                self.start_download(item)
                
        self.update_download_indicator()
        
    def start_download(self, item: DownloadQueueItem):
        """Запустить загрузку"""
        self.download_queue.is_downloading = True
        self.download_queue.current_download = item
        
        # Отображаем панель загрузки
        self.current_download_label.setText(f"Скачивание: {item.game.title}")
        self.download_progress.setValue(0)
        self.download_progress.setVisible(True)
        self.download_info.setVisible(True)
        self.cancel_download_btn.setVisible(True)
        self.download_panel.setVisible(True)

        # Запускаем загрузку в отдельном потоке
        self.download_thread = DownloadThread(item.download_url, item.game.title)
        self.download_thread.progress_updated.connect(self.on_download_progress)
        self.download_thread.download_finished.connect(self.on_download_finished)
        self.download_thread.start()
        
        
    def on_download_progress(self, downloaded: int, total: int, speed: float, eta: str, size_str: str):
        """Обновление прогресса загрузки"""
        if total > 0:
            progress = int((downloaded / total) * 100)
            self.download_progress.setValue(progress)
            
            info_text = f"Размер: {size_str}\nСкорость: {speed:.1f} МБ/с\nОсталось: {eta}"
            self.download_info.setText(info_text)
        
    def on_download_finished(self, success: bool, message: str):
        """Завершение загрузки"""
        self.download_queue.is_downloading = False
        self.download_queue.current_download = None

        self.current_download_label.setText("Нет активных загрузок")
        self.download_progress.setVisible(False)
        self.download_info.setVisible(False)
        self.cancel_download_btn.setVisible(False)

        if self.queue_list.count() > 0:
            self.queue_list.takeItem(0)

        if success:
            QMessageBox.information(self, "Загрузка завершена", message)
            self.refresh_downloaded_games()
        else:
            QMessageBox.warning(self, "Ошибка загрузки", message)
            
        # Ждем 10 секунд перед следующей загрузкой
        QTimer.singleShot(10000, self.process_download_queue)
        
    def cancel_download(self):
        """Отмена загрузки"""
        if hasattr(self, 'download_thread') and self.download_thread:
            self.download_thread.stop()

        self.download_queue.is_downloading = False
        self.download_queue.current_download = None

        self.current_download_label.setText("Нет активных загрузок")
        self.download_progress.setVisible(False)
        self.download_info.setVisible(False)
        self.cancel_download_btn.setVisible(False)

        QTimer.singleShot(1000, self.process_download_queue)
        self.update_download_indicator()
        
    def update_download_indicator(self):
        """Обновление индикатора загрузок"""
        queue_size = self.download_queue.get_queue_size()
        current = 1 if self.download_queue.is_downloading else 0
        
        if hasattr(self, 'download_indicator'):
            self.download_indicator.setText(f"Загрузок в очереди: {queue_size + current}")

        # Обновляем отображение очереди
        self.queue_list.clear()
        if self.download_queue.current_download:
            self.queue_list.addItem(f"⬇ {self.download_queue.current_download.game.title}")
        for q_item in list(self.download_queue.queue.queue):
            self.queue_list.addItem(f"⏳ {q_item.game.title}")
            
    def refresh_downloaded_games(self):
        """Обновить список скачанных игр"""
        downloads_dir = Path("downloads")
        self.downloaded_games_list.clear()
        
        if downloads_dir.exists():
            downloaded_files = list(downloads_dir.glob("*.wbfs")) + list(downloads_dir.glob("*.iso")) + list(downloads_dir.glob("*.rvz"))
            
            for file_path in downloaded_files:
                item = QListWidgetItem()
                file_size = file_path.stat().st_size / (1024**3)  # ГБ
                
                # Проверяем, установлена ли игра на флешке
                status_icon = "📥"
                if self.is_file_on_flash(file_path):
                    status_icon = "💾"
                
                item.setText(f"{status_icon} {file_path.stem}\n📦 {file_size:.2f} ГБ")
                item.setData(Qt.UserRole, file_path)
                
                font = QFont()
                font.setPointSize(10)
                font.setBold(True)
                item.setFont(font)
                
                self.downloaded_games_list.addItem(item)
                
        self.downloaded_stats.setText(f"Скачано: {self.downloaded_games_list.count()}")
        
    def is_file_on_flash(self, file_path: Path) -> bool:
        """Проверить, установлен ли файл на флешке"""
        if self.current_drive and self.flash_games:
            for flash_game in self.flash_games:
                if file_path.stem.lower() in flash_game.display_title.lower():
                    return True
        return False
        
    def refresh_drives(self):
        """Обновить список дисков"""
        self.drive_combo.clear()
        try:
            drives = Drive.get_drives()
            
            for drive in drives:
                # Безопасное форматирование - проверяем тип данных
                if hasattr(drive, 'available_space') and hasattr(drive, 'total_space'):
                    try:
                        available = float(drive.available_space) if drive.available_space else 0
                        total = float(drive.total_space) if drive.total_space else 0
                        self.drive_combo.addItem(f"{drive.name} ({available:.1f}/{total:.1f} ГБ)", drive)
                    except (ValueError, TypeError):
                        self.drive_combo.addItem(f"{drive.name} (размер неизвестен)", drive)
                else:
                    self.drive_combo.addItem(str(drive.name), drive)
        except Exception as e:
            print(f"Ошибка при получении дисков: {e}")
            self.drive_combo.addItem("Нет доступных дисков", None)
            
    def on_drive_changed(self):
        """Обработка смены диска"""
        current_data = self.drive_combo.currentData()
        if current_data:
            self.current_drive = current_data
            self.refresh_flash_games()
            
    def refresh_flash_games(self):
        """Обновить список игр на флешке"""
        if not self.current_drive:
            return
            
        self.flash_games_list.clear()
        self.flash_games = self.current_drive.get_games()
        
        for game in self.flash_games:
            item = QListWidgetItem()
            item.setText(f"💾 {game.display_title}\n� {game.size / (1024**3):.2f} ГБ")
            item.setData(Qt.UserRole, game)
            
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            item.setFont(font)
            
            self.flash_games_list.addItem(item)
            
        self.flash_stats.setText(f"Игр на флешке: {len(self.flash_games)}")
        
        # Обновляем отображение в других списках
        self.display_online_games(self.online_games)
        self.refresh_downloaded_games()
        
    def update_manager_stats(self):
        """Обновить статистику менеджера"""
        downloaded_count = self.downloaded_games_list.count()
        flash_count = self.flash_games_list.count()
        
        stats_text = f"Скачано: {downloaded_count} • На флешке: {flash_count}"
        
        if self.current_drive:
            stats_text += f" • Свободно: {self.current_drive.available_space:.1f} ГБ"
            
        self.manager_stats.setText(stats_text)
        
    def filter_manager_games(self):
        """Фильтровать игры в менеджере"""
        query = self.manager_search_input.text().lower()
        
        # Фильтруем скачанные игры
        for i in range(self.downloaded_games_list.count()):
            item = self.downloaded_games_list.item(i)
            item.setHidden(query not in item.text().lower())
            
        # Фильтруем игры на флешке
        for i in range(self.flash_games_list.count()):
            item = self.flash_games_list.item(i)
            item.setHidden(query not in item.text().lower())
            
    def setup_status_bar(self):
        """Настройка статус-бара"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Основной статус
        self.status_label = QLabel("Готов к работе")
        self.status_bar.addWidget(self.status_label)
        
        # Индикатор загрузки
        self.download_indicator = QLabel("Загрузок в очереди: 0")
        self.status_bar.addPermanentWidget(self.download_indicator)
        
    def setup_menu(self):
        """Настройка меню"""
        menubar = self.menuBar()
        
        # Файл
        file_menu = menubar.addMenu("Файл")
        
        load_html_action = QAction("Загрузить HTML файл", self)
        load_html_action.triggered.connect(self.load_html_file)
        file_menu.addAction(load_html_action)
        
        load_details_action = QAction("Загрузить детали игры", self)
        load_details_action.triggered.connect(self.load_details_file)
        file_menu.addAction(load_details_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Экспорт в JSON", self)
        export_action.triggered.connect(self.export_to_json)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Инструменты
        tools_menu = menubar.addMenu("Инструменты")
        
        clear_cache_action = QAction("Очистить кеш", self)
        clear_cache_action.triggered.connect(self.clear_cache)
        tools_menu.addAction(clear_cache_action)
        
        # Справка
        help_menu = menubar.addMenu("Справка")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def on_downloaded_game_selected(self, item: QListWidgetItem):
        """Обработка выбора скачанной игры"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            self.show_downloaded_game_card(file_path)
            
    def show_downloaded_game_card(self, file_path: Path):
        """Показать карточку скачанной игры"""
        # Очищаем предыдущую карточку
        for i in reversed(range(self.card_layout.count())):
            child = self.card_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
                
        # Создаем карточку для скачанной игры
        card = QWidget()
        card.setProperty("gameCard", True)
        card.setFixedSize(420, 500)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Название файла
        title_label = QLabel(file_path.stem)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                background-color: {WII_WHITE};
                border-radius: 8px;
                padding: 10px;
                border: 2px solid {WII_BLUE};
            }}
        """)
        layout.addWidget(title_label)
        
        # Информация о файле
        file_size = file_path.stat().st_size / (1024**3)  # ГБ
        file_modified = file_path.stat().st_mtime
        
        info_widget = QWidget()
        info_layout = QFormLayout(info_widget)
        info_layout.setSpacing(8)
        
        # Поля информации
        fields = [
            ("Файл:", file_path.name),
            ("Размер:", f"{file_size:.2f} ГБ"),
            ("Формат:", file_path.suffix.upper()),
            ("Путь:", str(file_path.parent)),
            ("Изменен:", time.strftime("%Y-%m-%d %H:%M", time.localtime(file_modified)))
        ]
        
        for label_text, value_text in fields:
            value_label = QLabel(value_text)
            value_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {WII_LIGHT_GRAY};
                    border: 1px solid {WII_GRAY};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }}
            """)
            info_layout.addRow(label_text, value_label)
            
        layout.addWidget(info_widget)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        install_btn = QPushButton("💾 Установить на флешку")
        install_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_GREEN};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid {WII_GREEN};
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #218838;
                border-color: #1e7e34;
            }}
        """)
        install_btn.clicked.connect(lambda: self.install_game_to_flash(file_path))
        
        delete_btn = QPushButton("🗑️ Удалить файл")
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_RED};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid {WII_RED};
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
                border-color: #bd2130;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.delete_game_file(file_path))
        
        buttons_layout.addWidget(install_btn)
        buttons_layout.addWidget(delete_btn)
        layout.addLayout(buttons_layout)
        
        self.card_layout.addWidget(card)
        
    def show_flash_game_card(self, game):
        """Показать карточку игры с флешки"""
        # Очищаем предыдущую карточку
        for i in reversed(range(self.card_layout.count())):
            child = self.card_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()
                
        # Создаем карточку для игры с флешки
        card = QWidget()
        card.setProperty("gameCard", True)
        card.setFixedSize(420, 400)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Название игры
        title_label = QLabel(f"💾 {game.display_title}")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {WII_BLUE};
                background-color: {WII_WHITE};
                border-radius: 8px;
                padding: 10px;
                border: 2px solid {WII_BLUE};
            }}
        """)
        layout.addWidget(title_label)
        
        # Информация об игре
        info_widget = QWidget()
        info_layout = QFormLayout(info_widget)
        info_layout.setSpacing(8)
        
        # Поля информации
        fields = [
            ("Размер:", f"{game.size / (1024**3):.2f} ГБ"),
            ("Тип:", game.type if hasattr(game, 'type') else "Неизвестно"),
            ("Путь:", game.path if hasattr(game, 'path') else "Неизвестно"),
        ]
        
        for label_text, value_text in fields:
            value_label = QLabel(value_text)
            value_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {WII_LIGHT_GRAY};
                    border: 1px solid {WII_GRAY};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }}
            """)
            info_layout.addRow(label_text, value_label)
            
        layout.addWidget(info_widget)
        
        # Кнопка удаления
        remove_btn = QPushButton("❌ Удалить с флешки")
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WII_RED};
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 2px solid {WII_RED};
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
                border-color: #bd2130;
            }}
        """)
        remove_btn.clicked.connect(lambda: self.remove_game_from_flash(game))
        layout.addWidget(remove_btn)
        
        self.card_layout.addWidget(card)
        self.card_layout.addStretch()
        
    def install_selected_to_flash(self):
        """Установить выбранную игру на флешку"""
        current_item = self.downloaded_games_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.UserRole)
            self.install_game_to_flash(file_path)
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите игру для установки")
            
    def install_game_to_flash(self, file_path: Path):
        """Установить игру на флешку"""
        if not self.current_drive:
            QMessageBox.warning(self, "Ошибка", "Выберите флешку")
            return
            
        self.copy_games_to_flash([str(file_path)])
        
    def delete_downloaded_game(self):
        """Удалить скачанную игру"""
        current_item = self.downloaded_games_list.currentItem()
        if current_item:
            file_path = current_item.data(Qt.UserRole)
            self.delete_downloaded_file(file_path)
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите игру для удаления")
            
    def delete_downloaded_file(self, file_path: Path):
        """Удалить скачанный файл"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Вы действительно хотите удалить файл '{file_path.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                file_path.unlink()
                self.refresh_downloaded_games()
                
                # Очищаем карточку
                for i in reversed(range(self.card_layout.count())):
                    child = self.card_layout.takeAt(i)
                    if child.widget():
                        child.widget().deleteLater()
                        
                QMessageBox.information(self, "Успех", "Файл удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл: {e}")
                
    def add_external_games(self):
        """Добавить внешние игры на флешку"""
        if not self.current_drive:
            QMessageBox.warning(self, "Ошибка", "Выберите флешку")
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите игры", "", "Файлы игр (*.iso *.wbfs *.rvz)"
        )
        
        if files:
            self.copy_games_to_flash(files)
            
    def copy_games_to_flash(self, files: List[str]):
        """Копирование игр на флешку"""
        if not self.current_drive:
            QMessageBox.warning(self, "Ошибка", "Выберите флешку")
            return
            
        # Показываем прогресс
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)
        
        # Запускаем копирование в отдельном потоке
        self.copy_thread = CopyThread(self.current_drive, files)
        self.copy_thread.progress_updated.connect(self.on_copy_progress)
        self.copy_thread.copy_finished.connect(self.on_copy_finished)
        self.copy_thread.start()
        
    def on_copy_progress(self, progress):
        """Обновление прогресса копирования"""
        if progress.total_files > 0:
            overall_percent = int((progress.files_completed / progress.total_files) * 100)
            self.download_progress.setValue(overall_percent)
            
    def on_copy_finished(self, success: bool, message: str):
        """Завершение копирования"""
        self.download_progress.setVisible(False)
        
        if success:
            QMessageBox.information(self, "Успех", message)
            self.refresh_flash_games()
        else:
            QMessageBox.warning(self, "Ошибка", message)
            
    def remove_from_flash(self):
        """Удалить выбранную игру с флешки"""
        current_item = self.flash_games_list.currentItem()
        if current_item:
            game = current_item.data(Qt.UserRole)
            self.delete_flash_game(game)
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите игру для удаления")
            
    def delete_flash_game(self, game: FlashGame):
        """Удалить игру с флешки"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Вы действительно хотите удалить игру '{game.display_title}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                game.delete()
                self.refresh_flash_games()
                
                # Очищаем карточку
                for i in reversed(range(self.card_layout.count())):
                    child = self.card_layout.takeAt(i)
                    if child.widget():
                        child.widget().deleteLater()
                        
                QMessageBox.information(self, "Успех", "Игра удалена")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить игру: {e}")
                
    def load_html_file(self):
        """Загрузить HTML файл"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите HTML файл", "", "HTML файлы (*.html)"
        )
        
        if file_path:
            try:
                games = self.parser.parse_search_results_from_file(file_path)
                self.online_games.extend(games)
                self.database.add_games(games)
                self.display_online_games(self.online_games)
                self.status_label.setText(f"Загружено игр из файла: {len(games)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {e}")
                
    def load_details_file(self):
        """Загрузить файл с деталями игры"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите HTML файл с деталями", "", "HTML файлы (*.html)"
        )
        
        if file_path:
            try:
                game = self.parser.parse_game_details_from_file(file_path)
                if game:
                    self.database.add_games([game])
                    self.status_label.setText(f"Загружены детали для игры: {game.title}")
                else:
                    QMessageBox.warning(self, "Предупреждение", "Не удалось извлечь детали игры")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {e}")
                
    def export_to_json(self):
        """Экспорт в JSON"""
        if not self.online_games:
            QMessageBox.warning(self, "Предупреждение", "Нет игр для экспорта")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить как", "wii_games_export.json", "JSON файлы (*.json)"
        )
        
        if file_path:
            try:
                games_data = [game.to_dict() for game in self.online_games]
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(games_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Успех", f"Экспорт завершен: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {e}")
                
    def clear_cache(self):
        """Очистить кеш"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            "Вы действительно хотите очистить кеш?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.database.games.clear()
            self.online_games.clear()
            self.online_games_list.clear()
            self.status_label.setText("Кеш очищен")
            
    def show_about(self):
        """Показать диалог о программе"""
        QMessageBox.about(self, "О программе", 
                         "🎮 Wii Unified Manager v1.0\n\n"
                         "Объединенный менеджер для поиска, загрузки и управления играми Nintendo Wii\n\n"
                         "✨ Возможности:\n"
                         "• Поиск игр онлайн\n"
                         "• Загрузка с детальным прогрессом\n"
                         "• Управление скачанными играми\n"
                         "• Установка игр на флешку\n"
                         "• Красивый интерфейс в стиле Nintendo\n\n"
                         "© 2025 Wii Unified Manager")
                         
    def perform_search(self):
        """Выполнить поиск игр"""
        query = self.search_input.text().strip()
        
        if not query:
            QMessageBox.warning(self, "Предупреждение", "Введите название игры для поиска")
            return
            
        # Очищаем предыдущие результаты
        self.online_games_list.clear()
        self.show_placeholder()
        
        # Показываем индикатор загрузки
        self.search_stats.setText("Поиск...")
        self.search_action_btn.setEnabled(False)
        self.search_action_btn.setText("Поиск...")
        
        # В реальном приложении здесь был бы поиск в интернете
        # Пока просто ищем в локальной базе
        try:
            results = self.database.search_games(query)
            self.online_games = results
            self.display_online_games(results)
            self.status_label.setText(f"Найдено {len(results)} игр по запросу: {query}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при поиске: {e}")
            self.search_stats.setText("Ошибка поиска")
        finally:
            self.search_action_btn.setEnabled(True)
            self.search_action_btn.setText("🔍 Найти")
            
    def on_flash_game_selected(self, item: QListWidgetItem):
        """Обработка выбора игры на флешке"""
        game = item.data(Qt.UserRole)
        if game:
            self.show_flash_game_card(game)
            
    def remove_game_from_flash(self, game):
        """Удалить игру с флешки"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Вы действительно хотите удалить игру '{game.display_title}' с флешки?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Удаление игры с флешки
                if hasattr(game, 'delete'):
                    game.delete()
                else:
                    # Альтернативный способ удаления
                    import os
                    if hasattr(game, 'path') and os.path.exists(game.path):
                        os.remove(game.path)
                        
                self.refresh_flash_games()
                self.show_placeholder()
                QMessageBox.information(self, "Успех", "Игра удалена с флешки")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить игру: {e}")
                
    def delete_game_file(self, file_path: Path):
        """Удалить файл игры"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Вы действительно хотите удалить файл '{file_path.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                file_path.unlink()
                self.refresh_downloaded_games()
                self.show_placeholder()
                QMessageBox.information(self, "Успех", "Файл удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл: {e}")
                
    def install_game_to_flash(self, file_path: Path):
        """Установить игру на флешку"""
        if not self.current_drive:
            QMessageBox.warning(self, "Ошибка", "Выберите флешку для установки")
            return
            
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Установить игру '{file_path.name}' на флешку?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Копирование файла на флешку
                import shutil
                dest_path = Path(self.current_drive.path) / file_path.name
                shutil.copy2(file_path, dest_path)
                
                self.refresh_flash_games()
                QMessageBox.information(self, "Успех", "Игра установлена на флешку")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить игру: {e}")
                         
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        # Сохраняем базу данных
        self.database.save_database()

        # Останавливаем все потоки
        if hasattr(self, 'download_thread') and self.download_thread:
            self.download_thread.stop()

        event.accept()

# Потоки для асинхронных операций
class ImageLoadThread(QThread):
    """Поток для загрузки изображений"""
    image_loaded = Signal(QPixmap)
    
    def __init__(self, url: str, target_size: QSize = None):
        super().__init__()
        self.url = url
        self.target_size = target_size or QSize(200, 200)
        
    def run(self):
        try:
            import requests
            
            # Исправляем URL если необходимо
            if self.url.startswith('//'):
                url = 'https:' + self.url
            elif self.url.startswith('/'):
                url = 'https://vimm.net' + self.url
            else:
                url = self.url
                
            # Создаем сессию с правильными заголовками
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://vimm.net/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            })
            
            # Обрабатываем base64 изображения
            if url.startswith('data:image'):
                import base64
                # Извлекаем base64 данные
                header, data = url.split(',', 1)
                image_data = base64.b64decode(data)
                
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.image_loaded.emit(scaled_pixmap)
                else:
                    self.image_loaded.emit(QPixmap())
                return
            
            # Загружаем обычное изображение
            response = session.get(url, timeout=15)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        self.target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.image_loaded.emit(scaled_pixmap)
                else:
                    self.image_loaded.emit(QPixmap())
            else:
                self.image_loaded.emit(QPixmap())
                
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            self.image_loaded.emit(QPixmap())

class SearchThread(QThread):
    """Поток для поиска игр"""
    results_ready = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, parser: WiiGameParser, query: str):
        super().__init__()
        self.parser = parser
        self.query = query
        
    def run(self):
        try:
            results = self.parser.search_games_online(self.query)
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))

class GameDetailsThread(QThread):
    """Поток для загрузки детальной информации об игре"""
    details_loaded = Signal(object)

    def __init__(self, parser: WiiGameParser, url: str):
        super().__init__()
        self.parser = parser
        self.url = url

    def run(self):
        game = self.parser.parse_game_details_from_url(self.url)
        if game:
            self.details_loaded.emit(game)

class DownloadThread(QThread):
    """Поток для загрузки игр с детальной информацией"""
    progress_updated = Signal(int, int, float, str, str)  # downloaded, total, speed, eta, filename
    download_finished = Signal(bool, str)
    
    def __init__(self, game_url: str, game_title: str):
        super().__init__()
        self.game_url = game_url
        self.game_title = game_title
        self.downloader = WiiGameSeleniumDownloader()
        self.should_stop = False
        self.start_time = None
        
    def run(self):
        try:
            self.start_time = time.time()
            
            def progress_callback(downloaded: int, total: int):
                if self.should_stop:
                    return
                    
                # Рассчитываем скорость и оставшееся время
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    speed = downloaded / elapsed / (1024 * 1024)  # МБ/с
                    if speed > 0:
                        remaining_bytes = total - downloaded
                        eta_seconds = remaining_bytes / (speed * 1024 * 1024)
                        eta_str = self.format_time(eta_seconds)
                    else:
                        eta_str = "Вычисляется..."
                else:
                    speed = 0
                    eta_str = "Вычисляется..."
                    
                # Форматируем размеры
                size_str = f"{downloaded / (1024**3):.2f} / {total / (1024**3):.2f} ГБ"
                
                self.progress_updated.emit(downloaded, total, speed, eta_str, size_str)
                    
            success = self.downloader.download_game(
                self.game_url, self.game_title, progress_callback
            )
            
            if success:
                files = self.downloader.get_downloaded_files()
                if files:
                    self.download_finished.emit(True, f"Игра '{self.game_title}' успешно скачана!\nФайл: {files[0].name}")
                else:
                    self.download_finished.emit(False, "Файл не найден после загрузки")
            else:
                self.download_finished.emit(False, f"Не удалось скачать игру '{self.game_title}'")
                
        except Exception as e:
            self.download_finished.emit(False, f"Ошибка при скачивании: {str(e)}")
            
    def format_time(self, seconds: float) -> str:
        """Форматирование времени"""
        if seconds < 60:
            return f"{int(seconds)} сек"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} мин"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}ч {minutes}м"
            
    def stop(self):
        self.should_stop = True
        if self.downloader:
            self.downloader.stop_download()

class CopyThread(QThread):
    """Поток для копирования игр на флешку"""
    progress_updated = Signal(object)  # CopyProgress object
    copy_finished = Signal(bool, str)  # success, message
    
    def __init__(self, drive, files):
        super().__init__()
        self.drive = drive
        self.files = [Path(f) for f in files]
        self.should_stop = False
        
    def run(self):
        try:
            # Импортируем здесь, чтобы избежать циклических импортов
            from wii_download_manager.models.enhanced_drive import CopyProgress
            
            def progress_callback(progress):
                if not self.should_stop:
                    self.progress_updated.emit(progress)
                    
            success = self.drive.add_games_with_progress(self.files, progress_callback)
            
            if success:
                self.copy_finished.emit(True, f"Успешно скопировано {len(self.files)} игр")
            else:
                self.copy_finished.emit(False, "Не удалось скопировать некоторые игры")
                
        except Exception as e:
            self.copy_finished.emit(False, f"Ошибка при копировании: {e}")
            
    def stop(self):
        self.should_stop = True

def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Настройка приложения
    app.setApplicationName("Wii Unified Manager")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Wii Tools")
    
    # Создание главного окна
    window = WiiUnifiedManager()
    window.show()
    
    # Запуск приложения
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
