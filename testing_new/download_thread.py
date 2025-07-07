#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Thread
==============
Handles real game downloading with progress tracking
"""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal
from wii_game_parser import WiiGame


class DownloadThread(QThread):
    """Поток для реальной загрузки игр с отслеживанием прогресса"""
    
    progress_updated = Signal(int, int, float, str, str)  # downloaded, total, speed MB/s, eta, size_str
    download_finished = Signal(bool, str)  # success, message
    
    def __init__(self, game: WiiGame):
        super().__init__()
        self.game = game
        self.should_stop = False
        self.start_time = None
        self.downloader = None

    def run(self):
        """Запуск загрузки"""
        try:
            # Импортируем загрузчик
            from wii_game_selenium_downloader import WiiGameSeleniumDownloader
            self.downloader = WiiGameSeleniumDownloader()

            total_size_bytes = self._parse_file_size(getattr(self.game, 'file_size', ''))

            self.start_time = time.time()

            def progress_callback(downloaded: int, total: int):
                """Callback для отслеживания прогресса"""
                if self.should_stop:
                    return
                    
                # Вычисляем скорость и время
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    speed_bps = downloaded / elapsed  # байт/сек
                    speed_mbs = speed_bps / (1024 * 1024)  # МБ/сек
                    
                    if speed_bps > 0 and total > downloaded:
                        remaining_bytes = total - downloaded
                        eta_seconds = remaining_bytes / speed_bps
                        eta_str = self._format_time(eta_seconds)
                    else:
                        eta_str = "Вычисляется..."
                else:
                    speed_mbs = 0
                    eta_str = "Вычисляется..."
                
                size_str = f"{downloaded / (1024**3):.2f} / {total / (1024**3):.2f} ГБ" if total > 0 else f"{downloaded / (1024**3):.2f} ГБ"
                self.progress_updated.emit(downloaded, total, speed_mbs, eta_str, size_str)
            
            # Проверяем, есть ли URL для скачивания
            if not hasattr(self.game, 'download_url') or not self.game.download_url:
                # Загружаем детальную информацию
                from wii_game_parser import WiiGameParser
                parser = WiiGameParser()
                detailed_game = parser.parse_game_details_from_url(self.game.detail_url)
                
                if detailed_game and hasattr(detailed_game, 'download_url') and detailed_game.download_url:
                    self.game.download_url = detailed_game.download_url
                else:
                    self.download_finished.emit(False, "Не удалось получить URL для скачивания")
                    return
            
            # Проверяем, есть ли уже скачанный файл
            if self._check_existing_file():
                self.download_finished.emit(True, f"Игра '{self.game.title}' уже скачана!")
                return
            
            # Начинаем скачивание
            success = self.downloader.download_game(
                self.game.detail_url,  # URL страницы игры
                self.game.title,       # Название игры
                game_id=getattr(self.game, 'id', None),  # ID игры
                progress_callback=progress_callback,      # Callback для прогресса
                stop_callback=lambda: self.should_stop,   # Callback для остановки
                total_size_bytes=total_size_bytes         # Ожидаемый размер файла
            )
            
            if success:
                files = self.downloader.get_downloaded_files()
                if files:
                    # Проверяем, нужно ли распаковать архив
                    extracted_files = self._extract_if_needed(files)
                    if extracted_files:
                        self.download_finished.emit(True, f"Игра '{self.game.title}' успешно скачана и распакована!")
                    else:
                        self.download_finished.emit(True, f"Игра '{self.game.title}' успешно скачана!")
                else:
                    self.download_finished.emit(False, "Файл не найден после загрузки")
            else:
                self.download_finished.emit(False, f"Не удалось скачать игру '{self.game.title}'")
                
        except Exception as e:
            self.download_finished.emit(False, f"Ошибка при скачивании: {str(e)}")

    def _format_time(self, seconds: float) -> str:
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
        """Остановка загрузки"""
        self.should_stop = True
        if self.downloader and hasattr(self.downloader, 'stop_download'):
            self.downloader.stop_download()

    def _check_existing_file(self) -> bool:
        """Проверяет, есть ли уже скачанный файл"""
        try:
            from pathlib import Path
            downloads_dir = Path("downloads")
            
            # Ищем файлы игры по названию
            game_title_clean = "".join(c for c in self.game.title if c.isalnum() or c in (' ', '-', '_')).strip()
            
            # Проверяем различные форматы файлов
            for ext in ['.iso', '.wbfs', '.rvz']:
                for file_path in downloads_dir.glob(f"*{game_title_clean}*{ext}"):
                    if file_path.exists():
                        print(f"Найден существующий файл: {file_path}")
                        return True
            # Если найден архив, пытаемся распаковать
            for file_path in downloads_dir.glob(f"*{game_title_clean}*.7z"):
                if file_path.exists():
                    print(f"Найден существующий архив: {file_path}")
                    self._extract_existing_archive(file_path)
                    return True
                        
            # Проверяем по ID игры, если есть
            if hasattr(self.game, 'id') and self.game.id:
                for ext in ['.iso', '.wbfs', '.rvz']:
                    for file_path in downloads_dir.glob(f"*{self.game.id}*{ext}"):
                        if file_path.exists():
                            print(f"Найден существующий файл по ID: {file_path}")
                            return True
                for file_path in downloads_dir.glob(f"*{self.game.id}*.7z"):
                    if file_path.exists():
                        print(f"Найден существующий архив по ID: {file_path}")
                        self._extract_existing_archive(file_path)
                        return True
                            
            return False
            
        except Exception as e:
            print(f"Ошибка проверки существующих файлов: {e}")
            return False

    def _extract_existing_archive(self, archive_path):
        """Распаковать существующий архив, если ещё не распакован"""
        try:
            from pathlib import Path
            import py7zr

            archive_path = Path(archive_path)
            extract_dir = archive_path.parent / archive_path.stem
            # Проверяем, есть ли уже распакованные файлы
            if not extract_dir.exists() or not list(extract_dir.glob('*.iso')) and not list(extract_dir.glob('*.wbfs')) and not list(extract_dir.glob('*.rvz')):
                extract_dir.mkdir(exist_ok=True)
                with py7zr.SevenZipFile(archive_path, mode='r') as archive:
                    archive.extractall(path=extract_dir)
                print(f"Архив {archive_path} распакован в {extract_dir}")
            else:
                print(f"Архив {archive_path} уже распакован")
        except Exception as e:
            print(f"Ошибка распаковки существующего архива {archive_path}: {e}")

    def _extract_if_needed(self, downloaded_files) -> list:
        """Извлекает архивы, если необходимо"""
        extracted_files = []
        
        try:
            from pathlib import Path
            import py7zr  # Потребуется установить: pip install py7zr
            
            for file_path in downloaded_files:
                file_path = Path(file_path)
                
                if file_path.suffix.lower() == '.7z':
                    print(f"Распаковка архива: {file_path}")
                    
                    extract_dir = file_path.parent / file_path.stem
                    extract_dir.mkdir(exist_ok=True)
                    
                    with py7zr.SevenZipFile(file_path, mode='r') as archive:
                        archive.extractall(path=extract_dir)
                    
                    # Ищем образы игр в распакованной папке
                    for ext in ['.iso', '.wbfs', '.rvz']:
                        for extracted_file in extract_dir.glob(f"*{ext}"):
                            extracted_files.append(str(extracted_file))
                            print(f"Извлечен образ игры: {extracted_file}")
                    
                    # Удаляем оригинальный архив после успешной распаковки
                    if extracted_files:
                        file_path.unlink()
                        print(f"Архив {file_path} удален после распаковки")
                else:
                    # Файл не является архивом
                    extracted_files.append(str(file_path))
                    
        except ImportError:
            print("Модуль py7zr не установлен. Архивы не будут распакованы автоматически.")
            print("Установите: pip install py7zr")
        except Exception as e:
            print(f"Ошибка распаковки архива: {e}")
            
        return extracted_files

    def _parse_file_size(self, size_str: str) -> int:
        """Преобразовать строку размера файла вида '4.3 GB' в байты"""
        try:
            if not size_str:
                return 0
            parts = size_str.replace(',', '').split()
            if not parts:
                return 0
            value = float(parts[0])
            unit = parts[1].lower() if len(parts) > 1 else ''
            if unit.startswith('gb'):
                return int(value * 1024 ** 3)
            if unit.startswith('mb'):
                return int(value * 1024 ** 2)
            if unit.startswith('kb'):
                return int(value * 1024)
            return int(value)
        except Exception:
            return 0
