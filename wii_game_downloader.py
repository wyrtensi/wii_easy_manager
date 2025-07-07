#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для загрузки игр Wii
Добавляет функциональность скачивания игр
"""

import os
import time
import logging
from typing import Optional, Callable
from pathlib import Path
import requests
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


class WiiGameDownloader:
    """Класс для загрузки игр Wii"""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Отключаем проверку SSL для проблемных сайтов
        self.session.verify = False
    
    def get_download_url(self, game_page_url: str) -> Optional[str]:
        """Получение прямой ссылки для скачивания игры"""
        try:
            response = self.session.get(game_page_url, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем форму для скачивания
            download_form = soup.find('form', {'id': 'dl_form'})
            if download_form:
                action = download_form.get('action', '')
                if action:
                    if action.startswith('//'):
                        action = 'https:' + action
                    elif action.startswith('/'):
                        action = urljoin(game_page_url, action)
                    return action
            
            # Альтернативный поиск ссылки для скачивания
            download_button = soup.find('button', {'type': 'submit'})
            if download_button:
                parent_form = download_button.find_parent('form')
                if parent_form:
                    action = parent_form.get('action', '')
                    if action:
                        if action.startswith('//'):
                            action = 'https:' + action
                        elif action.startswith('/'):
                            action = urljoin(game_page_url, action)
                        return action
            
            logger.warning(f"Не удалось найти ссылку для скачивания на странице: {game_page_url}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении ссылки для скачивания: {e}")
            return None
    
    def download_game(self, download_url: str, filename: str, 
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """
        Загрузка игры
        
        Args:
            download_url: URL для скачивания
            filename: Имя файла для сохранения
            progress_callback: Функция обратного вызова для отображения прогресса (downloaded, total)
        
        Returns:
            True если загрузка успешна, False иначе
        """
        try:
            file_path = self.download_dir / filename
            
            # Проверяем, не существует ли файл уже
            if file_path.exists():
                logger.info(f"Файл {filename} уже существует")
                return True
            
            logger.info(f"Начинаем загрузку: {filename}")
            
            # Получаем размер файла
            head_response = self.session.head(download_url, timeout=30)
            total_size = int(head_response.headers.get('content-length', 0))
            
            # Начинаем загрузку
            response = self.session.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            downloaded = 0
            chunk_size = 8192  # 8KB chunks
            
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        
                        # Вызываем callback для обновления прогресса
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"Загрузка завершена: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке {filename}: {e}")
            # Удаляем частично загруженный файл
            try:
                if file_path.exists():
                    file_path.unlink()
            except:
                pass
            return False
    
    def get_file_size_mb(self, file_size_str: str) -> float:
        """Конвертация строки размера файла в мегабайты"""
        try:
            if not file_size_str:
                return 0.0
            
            size_str = file_size_str.upper().strip()
            
            if 'GB' in size_str:
                return float(size_str.replace('GB', '').strip()) * 1024
            elif 'MB' in size_str:
                return float(size_str.replace('MB', '').strip())
            elif 'KB' in size_str:
                return float(size_str.replace('KB', '').strip()) / 1024
            else:
                # Попробуем извлечь число
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', size_str)
                if match:
                    return float(match.group(1))
                return 0.0
        except:
            return 0.0
    
    def generate_filename(self, game_title: str, region: str, file_format: str = "wbfs") -> str:
        """Генерация имени файла для игры"""
        # Очищаем название от недопустимых символов
        import re
        clean_title = re.sub(r'[<>:"/\\|?*]', '', game_title)
        clean_title = clean_title.strip()
        
        # Добавляем регион если есть
        if region and region != "Unknown":
            filename = f"{clean_title} ({region}).{file_format}"
        else:
            filename = f"{clean_title}.{file_format}"
        
        return filename
    
    def get_download_info(self, game_page_url: str) -> dict:
        """Получение информации о загрузке"""
        try:
            response = self.session.get(game_page_url, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            info = {
                'download_url': None,
                'file_size': None,
                'file_format': 'wbfs',
                'available': False
            }
            
            # Ищем размер файла по ID
            size_element = soup.find('td', {'id': 'dl_size'})
            if size_element:
                info['file_size'] = size_element.get_text(strip=True)
            else:
                # Альтернативный поиск размера файла в таблице
                size_found = False
                rows = soup.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        for cell in cells:
                            text = cell.get_text(strip=True)
                            # Поиск размера файла (например, "4.37 GB")
                            if text and ('GB' in text or 'MB' in text) and any(c.isdigit() for c in text):
                                # Проверяем, что это действительно размер файла
                                if '.' in text and text.replace('.', '').replace(' ', '').replace('GB', '').replace('MB', '').replace(',', '').isdigit():
                                    info['file_size'] = text
                                    size_found = True
                                    break
                    if size_found:
                        break
            
            # Ищем форму для скачивания
            download_form = soup.find('form', {'id': 'dl_form'})
            if download_form:
                action = download_form.get('action', '')
                if action:
                    if action.startswith('//'):
                        action = 'https:' + action
                    elif action.startswith('/'):
                        from urllib.parse import urljoin
                        action = urljoin(game_page_url, action)
                    
                    info['download_url'] = action
                    info['available'] = True
            
            # Если форма не найдена, ищем кнопку скачивания
            if not info['available']:
                download_button = soup.find('button', string=lambda x: x and 'Download' in x)
                if download_button:
                    parent_form = download_button.find_parent('form')
                    if parent_form:
                        action = parent_form.get('action', '')
                        if action:
                            if action.startswith('//'):
                                action = 'https:' + action
                            elif action.startswith('/'):
                                from urllib.parse import urljoin
                                action = urljoin(game_page_url, action)
                            
                            info['download_url'] = action
                            info['available'] = True
            
            return info
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о скачивании: {e}")
            return {
                'download_url': None,
                'file_size': None,
                'file_format': 'wbfs',
                'available': False
            }


def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла в читаемый вид"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_time_remaining(seconds: float) -> str:
    """Форматирование оставшегося времени"""
    if seconds < 60:
        return f"{int(seconds)} сек"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} мин"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}ч {minutes}м"
