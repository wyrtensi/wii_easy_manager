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
    
    progress_updated = Signal(int, int, float, str)  # downloaded, total, speed MB/s, eta
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
                
                self.progress_updated.emit(downloaded, total, speed_mbs, eta_str)
            
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
            
            # Определяем общий размер файла если возможно
            total_bytes = self._parse_file_size(getattr(self.game, "file_size", ""))

            # Начинаем скачивание
            success = self.downloader.download_game(
                self.game.detail_url,  # URL страницы игры
                self.game.title,       # Название игры
                game_id=getattr(self.game, 'id', None),  # ID игры
                progress_callback=progress_callback,      # Callback для прогресса
                stop_callback=lambda: self.should_stop,   # Callback для остановки
                total_size_bytes=total_bytes,
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
            for ext in ['.iso', '.wbfs', '.rvz', '.7z']:
                for file_path in downloads_dir.glob(f"*{game_title_clean}*{ext}"):
                    if file_path.exists():
                        print(f"Найден существующий файл: {file_path}")
                        if file_path.suffix.lower() == '.7z':
                            extracted = self._extract_if_needed([file_path])
                            if extracted:
                                self.game.local_path = extracted[0]
                        else:
                            self.game.local_path = str(file_path)
                        return True
                        
            # Проверяем по ID игры, если есть
            if hasattr(self.game, 'id') and self.game.id:
                for ext in ['.iso', '.wbfs', '.rvz', '.7z']:
                    for file_path in downloads_dir.glob(f"*{self.game.id}*{ext}"):
                        if file_path.exists():
                            print(f"Найден существующий файл по ID: {file_path}")
                            if file_path.suffix.lower() == '.7z':
                                extracted = self._extract_if_needed([file_path])
                                if extracted:
                                    self.game.local_path = extracted[0]
                            else:
                                self.game.local_path = str(file_path)
                            return True
                            
            return False
            
        except Exception as e:
            print(f"Ошибка проверки существующих файлов: {e}")
            return False

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
        """Преобразовать строку размера файла в байты."""
        import re
        if not size_str:
            return 0

        bytes_match = re.search(r"([\d,.]+)\s*bytes", size_str, re.I)
        if bytes_match:
            try:
                return int(bytes_match.group(1).replace(',', ''))
            except ValueError:
                pass

        match = re.search(r"([\d,.]+)\s*(GB|MB|KB)", size_str, re.I)
        if match:
            number = float(match.group(1).replace(',', '.'))
            unit = match.group(2).upper()
            factor = {'GB': 1024**3, 'MB': 1024**2, 'KB': 1024}.get(unit, 1)
            return int(number * factor)
        return 0
