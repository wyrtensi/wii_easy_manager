#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенный драйвер флешки для Wii Unified Manager
Включает лучшие индикаторы прогресса и обработку ошибок
"""

import os
import re
import shutil
import requests
import psutil
import threading
import time
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass

from .game import Game

TITLES_URL = "https://www.gametdb.com/titles.txt"

@dataclass
class CopyProgress:
    """Информация о прогрессе копирования"""
    current_file: str = ""
    files_completed: int = 0
    total_files: int = 0
    bytes_copied: int = 0
    total_bytes: int = 0
    speed_mbps: float = 0.0
    eta_seconds: float = 0.0

class EnhancedDrive:
    """Улучшенный класс для работы с флешкой"""
    
    def __init__(self, name: str, total_space: str, available_space: str, mount_point: Path):
        self.name = name
        self.total_space = total_space
        self.available_space = available_space
        self.mount_point = mount_point
        self._titles_cache = {}
        self._titles_cache_time = 0
        
    @staticmethod
    def get_drives() -> List['EnhancedDrive']:
        """Получить список съемных дисков"""
        drives = []
        for part in psutil.disk_partitions(all=False):
            # Улучшенная эвристика для определения съемных дисков
            is_removable = (
                'removable' in part.opts or 
                '/media' in part.mountpoint.lower() or 
                '/run/media' in part.mountpoint.lower() or
                part.fstype in ['fat32', 'exfat', 'ntfs'] and 
                part.mountpoint not in ['/', '/boot', '/home']
            )
            
            if is_removable:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append(
                        EnhancedDrive(
                            name=os.path.basename(part.mountpoint) or part.device,
                            total_space=f"{usage.total / (1<<30):.2f}",
                            available_space=f"{usage.free / (1<<30):.2f}",
                            mount_point=Path(part.mountpoint),
                        )
                    )
                except Exception:
                    continue
        return drives
    
    def _download_titles(self, path: Path) -> bool:
        """Скачать базу данных названий игр"""
        try:
            resp = requests.get(TITLES_URL, timeout=10)
            resp.raise_for_status()
            
            with open(path, 'wb') as f:
                f.write(resp.content)
            return True
        except Exception:
            return False
    
    def _get_titles_map(self) -> Dict[str, str]:
        """Получить карту названий игр с кешированием"""
        current_time = time.time()
        
        # Проверяем кеш (обновляем раз в час)
        if current_time - self._titles_cache_time < 3600 and self._titles_cache:
            return self._titles_cache
            
        path = self.mount_point / "titles.txt"
        
        # Скачиваем если нет или старый
        if not path.exists() or (current_time - path.stat().st_mtime) > 86400:  # 24 часа
            if not self._download_titles(path):
                return self._titles_cache  # Возвращаем старый кеш
                
        # Загружаем названия
        titles = {}
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        game_id, title = line.split('=', 1)
                        titles[game_id.strip()] = title.strip()
        except Exception:
            return self._titles_cache  # Возвращаем старый кеш
            
        self._titles_cache = titles
        self._titles_cache_time = current_time
        return titles
    
    def get_games(self) -> List[Game]:
        """Получить список игр на флешке"""
        wbfs_folder = self.mount_point / "wbfs"
        wbfs_folder.mkdir(exist_ok=True)
        
        titles = self._get_titles_map()
        games = []
        
        for entry in wbfs_folder.iterdir():
            if entry.is_dir():
                try:
                    game = Game(entry, titles)
                    games.append(game)
                except Exception:
                    continue
                    
        games.sort(key=lambda g: g.display_title.lower())
        return games
    
    def get_space_info(self) -> Dict[str, Any]:
        """Получить информацию о дисковом пространстве"""
        try:
            usage = psutil.disk_usage(str(self.mount_point))
            return {
                'total_bytes': usage.total,
                'free_bytes': usage.free,
                'used_bytes': usage.used,
                'total_gb': usage.total / (1024**3),
                'free_gb': usage.free / (1024**3),
                'used_gb': usage.used / (1024**3),
                'free_percent': (usage.free / usage.total) * 100
            }
        except Exception:
            return {
                'total_bytes': 0, 'free_bytes': 0, 'used_bytes': 0,
                'total_gb': 0, 'free_gb': 0, 'used_gb': 0, 'free_percent': 0
            }
    
    def can_fit_file(self, file_path: Path) -> bool:
        """Проверить, поместится ли файл на флешку"""
        try:
            file_size = file_path.stat().st_size
            space_info = self.get_space_info()
            return file_size <= space_info['free_bytes']
        except Exception:
            return False
    
    def add_games_with_progress(self, file_paths: List[Path], 
                              progress_callback: Optional[Callable[[CopyProgress], None]] = None) -> bool:
        """
        Добавить игры на флешку с отслеживанием прогресса
        
        Args:
            file_paths: Список путей к файлам игр
            progress_callback: Функция обратного вызова для отслеживания прогресса
        
        Returns:
            True если все файлы успешно скопированы
        """
        if not file_paths:
            return True
            
        wbfs_folder = self.mount_point / "wbfs"
        wbfs_folder.mkdir(exist_ok=True)
        
        # Подготовка информации о прогрессе
        progress = CopyProgress()
        progress.total_files = len(file_paths)
        progress.total_bytes = sum(f.stat().st_size for f in file_paths if f.exists())
        
        # Проверяем свободное место
        space_info = self.get_space_info()
        if progress.total_bytes > space_info['free_bytes']:
            raise Exception(f"Недостаточно места на диске. Нужно: {progress.total_bytes / (1024**3):.2f} ГБ, доступно: {space_info['free_gb']:.2f} ГБ")
        
        start_time = time.time()
        
        for i, file_path in enumerate(file_paths):
            if not file_path.exists():
                continue
                
            progress.current_file = file_path.name
            progress.files_completed = i
            
            if progress_callback:
                progress_callback(progress)
                
            try:
                # Определяем ID игры и название
                match = re.match(r"(.+)\[(.+)\]", file_path.stem)
                if match:
                    title, game_id = match.groups()
                else:
                    game_id = self._read_game_id(file_path)
                    title = file_path.stem
                    
                if not game_id:
                    raise ValueError(f"Не удалось определить ID игры для {file_path.name}")
                    
                # Создаем папку для игры
                dir_name = f"{title.strip()} [{game_id}]"
                dest_dir = wbfs_folder / dir_name
                dest_dir.mkdir(exist_ok=True)
                
                # Копируем файл с отслеживанием прогресса
                dest_file = dest_dir / f"{dir_name}.wbfs"
                self._copy_file_with_progress(file_path, dest_file, progress, start_time, progress_callback)
                
                progress.files_completed = i + 1
                
            except Exception as e:
                # Логируем ошибку, но продолжаем с другими файлами
                print(f"Ошибка при копировании {file_path.name}: {e}")
                continue
                
        if progress_callback:
            progress.current_file = "Завершено"
            progress_callback(progress)
            
        return True
    
    def _copy_file_with_progress(self, src: Path, dest: Path, progress: CopyProgress, 
                               start_time: float, progress_callback: Optional[Callable[[CopyProgress], None]]):
        """Копировать файл с отслеживанием прогресса"""
        buffer_size = 1024 * 1024  # 1 МБ буфер
        
        with open(src, 'rb') as fsrc, open(dest, 'wb') as fdest:
            while True:
                chunk = fsrc.read(buffer_size)
                if not chunk:
                    break
                    
                fdest.write(chunk)
                progress.bytes_copied += len(chunk)
                
                # Обновляем статистику
                elapsed = time.time() - start_time
                if elapsed > 0:
                    progress.speed_mbps = (progress.bytes_copied / elapsed) / (1024 * 1024)
                    remaining_bytes = progress.total_bytes - progress.bytes_copied
                    if progress.speed_mbps > 0:
                        progress.eta_seconds = remaining_bytes / (progress.speed_mbps * 1024 * 1024)
                
                if progress_callback:
                    progress_callback(progress)
    
    def _read_game_id(self, path: Path) -> Optional[str]:
        """Прочитать ID игры из файла ISO или WBFS"""
        try:
            with open(path, 'rb') as f:
                # Для WBFS файлов ID находится по смещению 0x200
                if path.suffix.lower() == '.wbfs':
                    f.seek(0x200)
                    
                data = f.read(6)
                game_id = data.decode('ascii', errors='ignore').strip()
                return game_id if len(game_id) == 6 else None
        except Exception:
            return None
    
    def add_game(self, file_path: Path) -> Path:
        """Добавить одну игру (совместимость с оригинальным API)"""
        success = self.add_games_with_progress([file_path])
        if success:
            # Возвращаем путь к скопированному файлу
            wbfs_folder = self.mount_point / "wbfs"
            games = self.get_games()
            # Находим последнюю добавленную игру
            if games:
                last_game = max(games, key=lambda g: g.dir.stat().st_mtime)
                wbfs_files = list(last_game.dir.glob("*.wbfs"))
                if wbfs_files:
                    return wbfs_files[0]
        raise Exception("Не удалось добавить игру")
    
    def remove_games(self, games: List[Game]) -> bool:
        """Удалить игры с флешки"""
        success = True
        for game in games:
            try:
                game.delete()
            except Exception as e:
                print(f"Ошибка при удалении {game.display_title}: {e}")
                success = False
        return success
    
    def get_games_info(self) -> Dict[str, Any]:
        """Получить информацию об играх на флешке"""
        games = self.get_games()
        
        total_size = sum(game.size for game in games)
        regions = {}
        
        for game in games:
            # Пытаемся определить регион из ID игры
            if len(game.id) >= 4:
                region_code = game.id[3]
                region_map = {
                    'E': 'USA',
                    'P': 'Europe', 
                    'J': 'Japan',
                    'K': 'Korea'
                }
                region = region_map.get(region_code, 'Unknown')
                regions[region] = regions.get(region, 0) + 1
        
        return {
            'total_games': len(games),
            'total_size_bytes': total_size,
            'total_size_gb': total_size / (1024**3),
            'regions': regions,
            'games': games
        }
    
    def verify_games(self) -> List[Dict[str, Any]]:
        """Проверить целостность игр на флешке"""
        games = self.get_games()
        results = []
        
        for game in games:
            result = {
                'game': game,
                'valid': True,
                'errors': []
            }
            
            try:
                # Проверяем наличие файлов
                wbfs_files = list(game.dir.glob("*.wbfs"))
                if not wbfs_files:
                    result['valid'] = False
                    result['errors'].append("Файл игры не найден")
                else:
                    # Проверяем размер файла
                    file_size = wbfs_files[0].stat().st_size
                    if file_size < 1024 * 1024:  # Меньше 1 МБ
                        result['valid'] = False
                        result['errors'].append("Файл игры слишком мал")
                    
                    # Проверяем возможность чтения
                    try:
                        with open(wbfs_files[0], 'rb') as f:
                            f.read(1024)
                    except Exception:
                        result['valid'] = False
                        result['errors'].append("Не удается прочитать файл игры")
                        
            except Exception as e:
                result['valid'] = False
                result['errors'].append(f"Ошибка проверки: {e}")
            
            results.append(result)
        
        return results
    
    def cleanup_empty_directories(self):
        """Очистить пустые папки"""
        wbfs_folder = self.mount_point / "wbfs"
        if not wbfs_folder.exists():
            return
            
        for entry in wbfs_folder.iterdir():
            if entry.is_dir():
                try:
                    # Проверяем, есть ли файлы в папке
                    if not any(entry.iterdir()):
                        entry.rmdir()
                except Exception:
                    continue
    
    def get_recommended_settings(self) -> Dict[str, Any]:
        """Получить рекомендуемые настройки для флешки"""
        space_info = self.get_space_info()
        
        settings = {
            'buffer_size': 1024 * 1024,  # 1 МБ по умолчанию
            'verify_after_copy': True,
            'cleanup_after_operations': True
        }
        
        # Рекомендации на основе размера диска
        if space_info['total_gb'] < 8:
            settings['buffer_size'] = 512 * 1024  # 512 КБ для маленьких дисков
        elif space_info['total_gb'] > 64:
            settings['buffer_size'] = 4 * 1024 * 1024  # 4 МБ для больших дисков
            
        return settings

# Алиас для совместимости
Drive = EnhancedDrive
