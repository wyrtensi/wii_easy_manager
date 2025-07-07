#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Графический интерфейс для парсера игр Wii
GUI для поиска и просмотра информации об играх Wii
"""

import sys
import os
from pathlib import Path
from typing import List, Optional
import webbrowser
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QTextEdit, QSplitter, QTabWidget, QGroupBox,
    QProgressBar, QStatusBar, QMenuBar, QMenu, QFileDialog,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QIcon, QFont, QAction, QDesktopServices
import requests

from wii_game_parser import WiiGameParser, WiiGameDatabase, WiiGame
from wii_game_downloader import WiiGameDownloader, format_file_size, format_time_remaining
from wii_game_selenium_downloader import WiiGameSeleniumDownloader


class GameDetailsDialog(QDialog):
    """Диалог для отображения подробной информации об игре"""
    
    def __init__(self, game: WiiGame, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle(f"Детали игры - {game.title}")
        self.setModal(True)
        self.resize(600, 500)
        
        self.setup_ui()
        self.load_game_info()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка "Общая информация"
        general_tab = QWidget()
        general_layout = QFormLayout()
        
        self.title_label = QLabel(self.game.title)
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        self.region_label = QLabel(self.game.region)
        self.version_label = QLabel(self.game.version)
        self.languages_label = QLabel(self.game.languages)
        self.rating_label = QLabel(self.game.rating)
        self.serial_label = QLabel(self.game.serial)
        self.players_label = QLabel(self.game.players)
        self.year_label = QLabel(self.game.year)
        self.file_size_label = QLabel(self.game.file_size)
        
        general_layout.addRow("Название:", self.title_label)
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
        
        self.graphics_label = QLabel(self.game.graphics)
        self.sound_label = QLabel(self.game.sound)
        self.gameplay_label = QLabel(self.game.gameplay)
        self.overall_label = QLabel(self.game.overall)
        self.crc_label = QLabel(self.game.crc)
        self.verified_label = QLabel(self.game.verified)
        
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
        
        # Обложка
        box_group = QGroupBox("Обложка")
        box_layout = QVBoxLayout()
        self.box_image = QLabel()
        self.box_image.setAlignment(Qt.AlignCenter)
        self.box_image.setMinimumSize(200, 280)
        self.box_image.setStyleSheet("border: 1px solid gray;")
        box_layout.addWidget(self.box_image)
        box_group.setLayout(box_layout)
        
        # Диск
        disc_group = QGroupBox("Диск")
        disc_layout = QVBoxLayout()
        self.disc_image = QLabel()
        self.disc_image.setAlignment(Qt.AlignCenter)
        self.disc_image.setMinimumSize(200, 200)
        self.disc_image.setStyleSheet("border: 1px solid gray;")
        disc_layout.addWidget(self.disc_image)
        disc_group.setLayout(disc_layout)
        
        images_layout.addWidget(box_group)
        images_layout.addWidget(disc_group)
        images_tab.setLayout(images_layout)
        tabs.addTab(images_tab, "Изображения")
        
        layout.addWidget(tabs)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Скачать игру")
        self.download_button.clicked.connect(self.download_game)
        
        self.open_url_button = QPushButton("Открыть на сайте")
        self.open_url_button.clicked.connect(self.open_game_url)
        
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.open_url_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
    
    def load_game_info(self):
        """Загрузка информации об игре"""
        # Загрузка изображений
        if self.game.box_art:
            self.load_image(self.game.box_art, self.box_image)
        else:
            self.box_image.setText("Нет изображения")
        
        if self.game.disc_art:
            self.load_image(self.game.disc_art, self.disc_image)
        else:
            self.disc_image.setText("Нет изображения")
        
        # Проверка URL
        if not self.game.detail_url:
            self.open_url_button.setEnabled(False)
    
    def load_image(self, url: str, label: QLabel):
        """Загрузка изображения по URL"""
        try:
            if url.startswith('data:'):
                # Обработка base64 изображений
                label.setText("Base64 изображение")
            else:
                # Загрузка обычного изображения
                response = requests.get(url, timeout=10)
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
            label.setText(f"Ошибка: {str(e)}")
    
    def open_game_url(self):
        """Открытие URL игры в браузере"""
        if self.game.detail_url:
            QDesktopServices.openUrl(self.game.detail_url)
    
    def download_game(self):
        """Открытие диалога загрузки игры"""
        download_dialog = DownloadDialog(self.game, self)
        download_dialog.exec()
    
    def load_game_details(self, game: WiiGame):
        """Загрузка детальной информации об игре"""
        if not game.detail_url:
            return
            
        try:
            # Загружаем детальную информацию
            game_details = self.parser.parse_game_details_from_url(game.detail_url)
            if game_details:
                # Обновляем игру детальной информацией
                game.serial = game_details.serial
                game.players = game_details.players
                game.year = game_details.year
                game.graphics = game_details.graphics
                game.sound = game_details.sound
                game.gameplay = game_details.gameplay
                game.overall = game_details.overall
                game.crc = game_details.crc
                game.verified = game_details.verified
                game.file_size = game_details.file_size
                game.box_art = game_details.box_art
                game.disc_art = game_details.disc_art
                game.download_urls = game_details.download_urls
                
                # Обновляем отображение
                self.show_game_info(game)
                
                # Сохраняем в базу данных
                self.database.save_database()
                
        except Exception as e:
            print(f"Ошибка при загрузке детальной информации: {e}")
    
    def clear_game_info(self):
        """Очистка панели информации"""
        self.info_text.clear()
        self.box_image.clear()
        self.box_image.setText("Обложка")
        self.disc_image.clear()
        self.disc_image.setText("Диск")
    

class SearchThread(QThread):
    """Поток для выполнения поиска"""
    
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


class DownloadThread(QThread):
    """Поток для загрузки игр с использованием Selenium"""
    
    progress_updated = Signal(float, float)  # downloaded, total в MB
    download_finished = Signal(bool, str)  # success, message
    
    def __init__(self, game_url: str, game_title: str):
        super().__init__()
        self.game_url = game_url
        self.game_title = game_title
        self.downloader = WiiGameSeleniumDownloader()
    
    def run(self):
        def progress_callback(downloaded: int, total: int):
            # Конвертируем в MB для избежания overflow
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.progress_updated.emit(downloaded_mb, total_mb)
        
        try:
            success = self.downloader.download_game(
                self.game_url, 
                self.game_title,
                progress_callback
            )
            
            if success:
                files = self.downloader.get_downloaded_files()
                if files:
                    self.download_finished.emit(True, f"Загрузка завершена: {files[0].name}")
                else:
                    self.download_finished.emit(False, "Файл не найден после загрузки")
            else:
                self.download_finished.emit(False, f"Ошибка при загрузке: {self.game_title}")
                
        except Exception as e:
            self.download_finished.emit(False, f"Ошибка загрузки: {str(e)}")
    
    def stop(self):
        """Остановка загрузки"""
        if self.downloader:
            self.downloader.stop_download()


class DownloadDialog(QDialog):
    """Диалог для загрузки игры"""
    
    def __init__(self, game: WiiGame, parent=None):
        super().__init__(parent)
        self.game = game
        self.downloader = WiiGameDownloader()
        self.download_thread = None
        
        self.setWindowTitle(f"Загрузка - {game.title}")
        self.setModal(True)
        self.resize(500, 200)
        
        self.setup_ui()
        self.load_download_info()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        
        # Информация об игре
        info_label = QLabel(f"<b>{self.game.title}</b> ({self.game.region})")
        info_label.setFont(QFont("Arial", 12))
        layout.addWidget(info_label)
        
        # Информация о файле
        self.file_info_label = QLabel("Получение информации о файле...")
        layout.addWidget(self.file_info_label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Статус
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Скачать")
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.cancel_download)
        
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.close_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
    
    def load_download_info(self):
        """Загрузка информации о файле для скачивания"""
        if not self.game.detail_url:
            self.file_info_label.setText("URL страницы игры не найден")
            return
        
        try:
            download_info = self.downloader.get_download_info(self.game.detail_url)
            
            if download_info['available']:
                size_text = download_info['file_size'] or "Размер неизвестен"
                format_text = download_info['file_format'].upper()
                
                self.file_info_label.setText(
                    f"Размер: {size_text} | Формат: {format_text}"
                )
                
                self.download_url = download_info['download_url']
                self.filename = self.downloader.generate_filename(
                    self.game.title, 
                    self.game.region, 
                    download_info['file_format']
                )
                
                self.download_button.setEnabled(True)
                self.status_label.setText("Готов к загрузке")
            else:
                self.file_info_label.setText("Файл недоступен для загрузки")
                self.status_label.setText("Загрузка недоступна")
                
        except Exception as e:
            self.file_info_label.setText(f"Ошибка: {str(e)}")
            self.status_label.setText("Ошибка получения информации")
    
    def start_download(self):
        """Начало загрузки"""
        if not self.game.detail_url:
            QMessageBox.warning(self, "Ошибка", "URL страницы игры не найден")
            return
        
        # Отключаем кнопку загрузки
        self.download_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        
        # Запускаем загрузку в отдельном потоке
        self.download_thread = DownloadThread(
            self.game.detail_url, 
            self.game.title
        )
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.download_finished.connect(self.download_completed)
        self.download_thread.start()
        
        self.status_label.setText("Загружается...")
    
    def update_progress(self, downloaded: int, total: int):
        """Обновление прогресса загрузки"""
        if total > 0:
            percentage = int((downloaded / total) * 100)
            self.progress_bar.setValue(percentage)
            
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            self.status_label.setText(
                f"Загружается: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percentage}%)"
            )
    
    def download_completed(self, success: bool, message: str):
        """Завершение загрузки"""
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
        
        if success:
            self.status_label.setText("Загрузка завершена успешно!")
            QMessageBox.information(self, "Успех", message)
        else:
            self.status_label.setText("Ошибка загрузки")
            QMessageBox.critical(self, "Ошибка", message)
    
    def cancel_download(self):
        """Отмена загрузки"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.terminate()
            self.download_thread.wait()
            self.status_label.setText("Загрузка отменена")
            self.progress_bar.setVisible(False)
            self.download_button.setEnabled(True)
        else:
            self.accept()


class WiiGameBrowser(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wii Game Browser - Браузер игр Wii")
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация компонентов
        self.parser = WiiGameParser()
        self.database = WiiGameDatabase()
        self.downloader = WiiGameDownloader()
        self.current_games: List[WiiGame] = []
        self.download_thread: Optional[DownloadThread] = None
        
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        
        # Загрузка данных
        self.load_local_games()
        
        # Настройка таймера для автосохранения
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.database.save_database)
        self.autosave_timer.start(300000)  # Автосохранение каждые 5 минут
    
    def setup_ui(self):
        """Настройка интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Панель поиска
        search_layout = QHBoxLayout()
        
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название игры...")
        self.search_input.returnPressed.connect(self.search_games)
        search_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton("Поиск")
        self.search_button.clicked.connect(self.search_games)
        search_layout.addWidget(self.search_button)
        
        self.online_search_button = QPushButton("Поиск онлайн")
        self.online_search_button.clicked.connect(self.search_online)
        search_layout.addWidget(self.online_search_button)
        
        layout.addLayout(search_layout)
        
        # Панель фильтров
        filters_layout = QHBoxLayout()
        
        filters_layout.addWidget(QLabel("Регион:"))
        self.region_filter = QComboBox()
        self.region_filter.addItems(["Все", "USA", "Europe", "Japan", "Asia"])
        self.region_filter.currentTextChanged.connect(self.apply_filters)
        filters_layout.addWidget(self.region_filter)
        
        filters_layout.addWidget(QLabel("Рейтинг:"))
        self.rating_filter = QComboBox()
        self.rating_filter.addItems(["Все", "E", "T", "M", "K-A", "E10+"])
        self.rating_filter.currentTextChanged.connect(self.apply_filters)
        filters_layout.addWidget(self.rating_filter)
        
        filters_layout.addStretch()
        
        self.clear_filters_button = QPushButton("Сбросить фильтры")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters_layout.addWidget(self.clear_filters_button)
        
        layout.addLayout(filters_layout)
        
        # Основная область с таблицей
        splitter = QSplitter(Qt.Horizontal)
        
        # Таблица игр
        self.games_table = QTableWidget()
        self.games_table.setColumnCount(5)
        self.games_table.setHorizontalHeaderLabels([
            "Название", "Регион", "Версия", "Языки", "Рейтинг"
        ])
        self.games_table.horizontalHeader().setStretchLastSection(True)
        self.games_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.games_table.setAlternatingRowColors(True)
        self.games_table.doubleClicked.connect(self.show_game_details)
        
        splitter.addWidget(self.games_table)
        
        # Панель информации
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        
        self.info_label = QLabel("Информация об игре")
        self.info_label.setFont(QFont("Arial", 10, QFont.Bold))
        info_layout.addWidget(self.info_label)
        
        # Создаем прокручиваемую область для информации
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Виджет с информацией
        self.info_content = QWidget()
        self.info_content_layout = QVBoxLayout()
        
        # Изображения
        images_layout = QHBoxLayout()
        
        # Обложка
        self.box_image = QLabel()
        self.box_image.setAlignment(Qt.AlignCenter)
        self.box_image.setFixedSize(122, 170)  # Уменьшенный размер
        self.box_image.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.box_image.setText("Обложка")
        
        # Диск
        self.disc_image = QLabel()
        self.disc_image.setAlignment(Qt.AlignCenter)
        self.disc_image.setFixedSize(80, 80)  # Уменьшенный размер
        self.disc_image.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.disc_image.setText("Диск")
        
        images_layout.addWidget(self.box_image)
        images_layout.addWidget(self.disc_image)
        images_layout.addStretch()
        
        self.info_content_layout.addLayout(images_layout)
        
        # Текстовая информация
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(250)
        self.info_content_layout.addWidget(self.info_text)
        
        # Прогресс загрузки
        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        self.info_content_layout.addWidget(self.download_progress)
        
        # Статус загрузки
        self.download_status = QLabel("")
        self.download_status.setVisible(False)
        self.info_content_layout.addWidget(self.download_status)
        
        self.info_content.setLayout(self.info_content_layout)
        scroll_area.setWidget(self.info_content)
        info_layout.addWidget(scroll_area)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Скачать")
        self.download_button.clicked.connect(self.download_selected_game)
        self.download_button.setEnabled(False)
        
        self.cancel_download_button = QPushButton("Отменить")
        self.cancel_download_button.clicked.connect(self.cancel_download)
        self.cancel_download_button.setEnabled(False)
        self.cancel_download_button.setVisible(False)
        
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.cancel_download_button)
        info_layout.addLayout(buttons_layout)
        
        info_widget.setLayout(info_layout)
        info_widget.setMaximumWidth(350)
        splitter.addWidget(info_widget)
        
        layout.addWidget(splitter)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        central_widget.setLayout(layout)
        
        # Подключение сигналов
        self.games_table.itemSelectionChanged.connect(self.on_selection_changed)
    
    def setup_menu(self):
        """Настройка меню"""
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")
        
        load_action = QAction("Загрузить HTML файл", self)
        load_action.triggered.connect(self.load_html_file)
        file_menu.addAction(load_action)
        
        load_details_action = QAction("Загрузить файл с деталями", self)
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
        
        # Меню "Справка"
        help_menu = menubar.addMenu("Справка")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Настройка строки состояния"""
        self.statusBar().showMessage("Готов")
    
    def load_local_games(self):
        """Загрузка локальных игр"""
        self.current_games = self.database.games
        self.update_games_table()
        self.statusBar().showMessage(f"Загружено {len(self.current_games)} игр")
    
    def search_games(self):
        """Поиск игр в локальной базе"""
        query = self.search_input.text().strip()
        
        if not query:
            self.load_local_games()
            return
        
        results = self.database.search_games(query)
        self.current_games = results
        self.update_games_table()
        self.statusBar().showMessage(f"Найдено {len(results)} игр по запросу: {query}")
    
    def search_online(self):
        """Онлайн поиск игр"""
        query = self.search_input.text().strip()
        
        if not query:
            QMessageBox.warning(self, "Предупреждение", "Введите запрос для поиска")
            return
        
        # Отключаем кнопку и показываем прогресс
        self.online_search_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
        
        # Запускаем поиск в отдельном потоке
        self.search_thread = SearchThread(self.parser, query)
        self.search_thread.results_ready.connect(self.on_search_results)
        self.search_thread.error_occurred.connect(self.on_search_error)
        self.search_thread.start()
    
    def on_search_results(self, results: List[WiiGame]):
        """Обработка результатов онлайн поиска"""
        self.online_search_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if results:
            # Добавляем новые игры в базу данных
            self.database.add_games(results)
            self.current_games = results
            self.update_games_table()
            self.statusBar().showMessage(f"Найдено {len(results)} игр онлайн")
        else:
            QMessageBox.information(self, "Результаты поиска", "Игры не найдены")
            self.statusBar().showMessage("Игры не найдены")
    
    def on_search_error(self, error: str):
        """Обработка ошибки поиска"""
        self.online_search_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if "SSL" in error:
            QMessageBox.warning(
                self, "Проблема с SSL сертификатом", 
                "Не удается подключиться к сайту vimm.net из-за проблем с SSL сертификатом.\n\n"
                "Рекомендации:\n"
                "1. Используйте локальные HTML файлы (Меню → Файл → Загрузить HTML файл)\n"
                "2. Сохраните страницы поиска с сайта vimm.net вручную\n"
                "3. Проверьте настройки антивируса/файрвола"
            )
        else:
            QMessageBox.critical(self, "Ошибка поиска", f"Ошибка при поиске: {error}")
        
        self.statusBar().showMessage("Ошибка онлайн поиска - используйте локальные файлы")
    
    def apply_filters(self):
        """Применение фильтров"""
        region = self.region_filter.currentText()
        rating = self.rating_filter.currentText()
        
        filtered_games = self.database.games
        
        if region != "Все":
            filtered_games = [g for g in filtered_games if g.region == region]
        
        if rating != "Все":
            filtered_games = [g for g in filtered_games if g.rating == rating]
        
        self.current_games = filtered_games
        self.update_games_table()
        self.statusBar().showMessage(f"Показано {len(filtered_games)} игр")
    
    def clear_filters(self):
        """Сброс фильтров"""
        self.region_filter.setCurrentText("Все")
        self.rating_filter.setCurrentText("Все")
        self.search_input.clear()
        self.load_local_games()
    
    def update_games_table(self):
        """Обновление таблицы игр"""
        self.games_table.setRowCount(len(self.current_games))
        
        for row, game in enumerate(self.current_games):
            self.games_table.setItem(row, 0, QTableWidgetItem(game.title))
            self.games_table.setItem(row, 1, QTableWidgetItem(game.region))
            self.games_table.setItem(row, 2, QTableWidgetItem(game.version))
            self.games_table.setItem(row, 3, QTableWidgetItem(game.languages))
            self.games_table.setItem(row, 4, QTableWidgetItem(game.rating))
        
        # Автоматическое изменение размера столбцов
        self.games_table.resizeColumnsToContents()
    
    def on_selection_changed(self):
        """Обработка изменения выбора в таблице"""
        selected_rows = self.games_table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.current_games):
                game = self.current_games[row]
                self.show_game_info(game)
                self.download_button.setEnabled(True)
                
                # Автоматически загружаем детальную информацию, если она еще не загружена
                if game.detail_url and not game.year:  # Если детали еще не загружены
                    self.load_game_details(game)
            else:
                self.download_button.setEnabled(False)
        else:
            self.download_button.setEnabled(False)
            self.clear_game_info()
    
    def load_game_details(self, game: WiiGame):
        """Загрузка детальной информации об игре"""
        if not game.detail_url:
            return
            
        try:
            # Загружаем детальную информацию
            game_details = self.parser.parse_game_details_from_url(game.detail_url)
            if game_details:
                # Обновляем игру детальной информацией
                game.serial = game_details.serial
                game.players = game_details.players
                game.year = game_details.year
                game.graphics = game_details.graphics
                game.sound = game_details.sound
                game.gameplay = game_details.gameplay
                game.overall = game_details.overall
                game.crc = game_details.crc
                game.verified = game_details.verified
                game.file_size = game_details.file_size
                game.box_art = game_details.box_art
                game.disc_art = game_details.disc_art
                game.download_urls = game_details.download_urls
                
                # Обновляем отображение
                self.show_game_info(game)
                
                # Сохраняем в базу данных
                self.database.save_database()
                
        except Exception as e:
            print(f"Ошибка при загрузке детальной информации: {e}")
    
    def clear_game_info(self):
        """Очистка панели информации"""
        self.info_text.clear()
        self.box_image.clear()
        self.box_image.setText("Обложка")
        self.disc_image.clear()
        self.disc_image.setText("Диск")
    
    def show_game_info(self, game: WiiGame):
        """Отображение информации об игре"""
        info_text = f"""
<b>Название:</b> {game.title}<br>
<b>Регион:</b> {game.region}<br>
<b>Версия:</b> {game.version}<br>
<b>Языки:</b> {game.languages}<br>
<b>Рейтинг:</b> {game.rating}<br>
"""
        
        if game.year:
            info_text += f"<b>Год:</b> {game.year}<br>"
        if game.players:
            info_text += f"<b>Игроки:</b> {game.players}<br>"
        if game.serial:
            info_text += f"<b>Серийный номер:</b> {game.serial}<br>"
        if game.file_size:
            info_text += f"<b>Размер:</b> {game.file_size}<br>"
        
        # Рейтинги
        if game.graphics or game.sound or game.gameplay or game.overall:
            info_text += "<br><b>Оценки:</b><br>"
            if game.graphics:
                info_text += f"• Графика: {game.graphics}<br>"
            if game.sound:
                info_text += f"• Звук: {game.sound}<br>"
            if game.gameplay:
                info_text += f"• Геймплей: {game.gameplay}<br>"
            if game.overall:
                info_text += f"• Общий рейтинг: {game.overall}<br>"
        
        if game.crc:
            info_text += f"<br><b>CRC:</b> {game.crc}<br>"
        if game.verified:
            info_text += f"<b>Проверено:</b> {game.verified}<br>"
        
        self.info_text.setHtml(info_text)
        
        # Загрузка изображений
        self.load_game_images(game)
    
    def load_game_images(self, game: WiiGame):
        """Загрузка изображений игры"""
        # Загрузка обложки
        if game.box_art:
            self.load_image_async(game.box_art, self.box_image)
        else:
            self.box_image.clear()
            self.box_image.setText("Обложка")
        
        # Загрузка диска
        if game.disc_art:
            self.load_image_async(game.disc_art, self.disc_image)
        else:
            self.disc_image.clear()
            self.disc_image.setText("Диск")
    
    def load_image_async(self, url: str, label: QLabel):
        """Асинхронная загрузка изображения"""
        def load_image_with_session():
            try:
                # Если это base64 изображение
                if url.startswith('data:image'):
                    import base64
                    # Извлекаем base64 данные
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
                        label.setText("Ошибка")
                    return
                
                # Обычная загрузка изображения
                if url.startswith('//'):
                    url_fixed = 'https:' + url
                elif url.startswith('/'):
                    url_fixed = 'https://vimm.net' + url
                else:
                    url_fixed = url
                
                # Создаем сессию с правильными заголовками
                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://vimm.net/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'image',
                    'Sec-Fetch-Mode': 'no-cors',
                    'Sec-Fetch-Site': 'same-origin'
                })
                session.verify = False
                
                response = session.get(url_fixed, timeout=15)
                if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        label.setPixmap(scaled_pixmap)
                        return
                
                # Если изображение не загрузилось, показываем текст
                label.setText("Нет изображения")
                
            except Exception as e:
                label.setText("Ошибка")
                print(f"Ошибка загрузки изображения {url}: {e}")
        
        # Запускаем в отдельном потоке
        import threading
        thread = threading.Thread(target=load_image_with_session)
        thread.daemon = True
        thread.start()
    
    def show_game_details(self):
        """Показ подробной информации об игре"""
        selected_rows = self.games_table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.current_games):
                game = self.current_games[row]
                dialog = GameDetailsDialog(game, self)
                dialog.exec()
    
    def download_selected_game(self):
        """Скачать выбранную игру"""
        selected_rows = self.games_table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.current_games):
                game = self.current_games[row]
                
                if not game.detail_url:
                    QMessageBox.warning(self, "Ошибка", "URL страницы игры не найден")
                    return
                
                # Показываем элементы загрузки
                self.download_progress.setVisible(True)
                self.download_progress.setRange(0, 100)
                self.download_progress.setValue(0)
                self.download_status.setVisible(True)
                self.download_status.setText("Подготовка к загрузке...")
                
                # Переключаем кнопки
                self.download_button.setEnabled(False)
                self.cancel_download_button.setVisible(True)
                self.cancel_download_button.setEnabled(True)
                
                # Запускаем загрузку
                self.download_thread = DownloadThread(game.detail_url, game.title)
                self.download_thread.progress_updated.connect(self.update_download_progress)
                self.download_thread.download_finished.connect(self.download_completed)
                self.download_thread.start()
    
    def update_download_progress(self, downloaded_mb: float, total_mb: float):
        """Обновление прогресса загрузки"""
        if total_mb > 0:
            percentage = int((downloaded_mb / total_mb) * 100)
            self.download_progress.setValue(percentage)
            self.download_status.setText(
                f"Загружено: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percentage}%)"
            )
        else:
            self.download_status.setText(f"Загружено: {downloaded_mb:.1f} MB")
    
    def download_completed(self, success: bool, message: str):
        """Завершение загрузки"""
        self.download_progress.setVisible(False)
        self.download_button.setEnabled(True)
        self.cancel_download_button.setVisible(False)
        self.cancel_download_button.setEnabled(False)
        
        if success:
            self.download_status.setText("Загрузка завершена успешно!")
            QMessageBox.information(self, "Успех", message)
        else:
            self.download_status.setText("Ошибка загрузки")
            QMessageBox.critical(self, "Ошибка", message)
        
        self.download_thread = None
    
    def cancel_download(self):
        """Отмена загрузки"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait()
            
            self.download_progress.setVisible(False)
            self.download_status.setText("Загрузка отменена")
            self.download_button.setEnabled(True)
            self.cancel_download_button.setVisible(False)
            self.cancel_download_button.setEnabled(False)
            
            self.download_thread = None
    
    def load_html_file(self):
        """Загрузка HTML файла с результатами поиска"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите HTML файл", "",
            "HTML files (*.html);;All files (*)"
        )
        
        if file_path:
            try:
                games = self.parser.parse_search_results_from_file(file_path)
                if games:
                    self.database.add_games(games)
                    self.current_games = games
                    self.update_games_table()
                    QMessageBox.information(
                        self, "Успех", 
                        f"Загружено {len(games)} игр из файла"
                    )
                else:
                    QMessageBox.warning(
                        self, "Предупреждение",
                        "Не удалось найти игры в файле"
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Ошибка при загрузке файла: {str(e)}"
                )
    
    def load_details_file(self):
        """Загрузка HTML файла с деталями игры"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите HTML файл с деталями", "",
            "HTML files (*.html);;All files (*)"
        )
        
        if file_path:
            try:
                game_details = self.parser.parse_game_details_from_file(file_path)
                if game_details:
                    # Ищем существующую игру или создаем новую
                    existing_game = self.database.find_game_by_title(game_details.title)
                    if existing_game:
                        # Обновляем существующую игру
                        existing_game.serial = game_details.serial
                        existing_game.players = game_details.players
                        existing_game.year = game_details.year
                        existing_game.graphics = game_details.graphics
                        existing_game.sound = game_details.sound
                        existing_game.gameplay = game_details.gameplay
                        existing_game.overall = game_details.overall
                        existing_game.crc = game_details.crc
                        existing_game.verified = game_details.verified
                        existing_game.file_size = game_details.file_size
                        existing_game.box_art = game_details.box_art
                        existing_game.disc_art = game_details.disc_art
                    else:
                        # Добавляем новую игру
                        self.database.add_games([game_details])
                    
                    self.database.save_database()
                    self.update_games_table()
                    QMessageBox.information(
                        self, "Успех",
                        f"Детальная информация для игры '{game_details.title}' загружена"
                    )
                else:
                    QMessageBox.warning(
                        self, "Предупреждение",
                        "Не удалось извлечь детальную информацию из файла"
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Ошибка при загрузке файла: {str(e)}"
                )
    
    def export_to_json(self):
        """Экспорт данных в JSON"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить как JSON", "wii_games_export.json",
            "JSON files (*.json);;All files (*)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump([game.to_dict() for game in self.current_games],
                             file, indent=2, ensure_ascii=False)
                QMessageBox.information(
                    self, "Успех",
                    f"Экспортировано {len(self.current_games)} игр в {file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Ошибка при экспорте: {str(e)}"
                )
    
    def show_about(self):
        """Показ информации о программе"""
        QMessageBox.about(
            self, "О программе",
            """
            <h3>Wii Game Browser</h3>
            <p>Парсер и браузер игр для Nintendo Wii</p>
            <p>Версия 1.0</p>
            <p>Позволяет парсить и просматривать информацию об играх Wii с сайта vimm.net</p>
            <p><b>Возможности:</b></p>
            <ul>
                <li>Парсинг HTML файлов с результатами поиска</li>
                <li>Извлечение детальной информации об играх</li>
                <li>Онлайн поиск игр</li>
                <li>Фильтрация по регионам и рейтингам</li>
                <li>Экспорт данных в JSON</li>
            </ul>
            """
        )
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        # Сохраняем базу данных перед закрытием
        self.database.save_database()
        event.accept()


def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Устанавливаем иконку приложения (если есть)
    app.setApplicationName("Wii Game Browser")
    app.setApplicationVersion("1.0")
    
    # Создаем и показываем главное окно
    window = WiiGameBrowser()
    window.show()
    
    # Запускаем приложение
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
