#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер конфигурации для Wii Unified Manager
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """Менеджер конфигурации приложения"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_default_config()
        self._load_config()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации по умолчанию"""
        return {
            "app_name": "Wii Unified Manager",
            "version": "2.0.0",
            "ui_settings": {
                "theme": "wii_blue",
                "card_size": {"width": 300, "height": 400},
                "image_size": {"width": 250, "height": 150},
                "colors": {
                    "primary": "#1E90FF",
                    "secondary": "#87CEEB",
                    "background": "#FFFFFF",
                    "text": "#2C3E50",
                    "accent": "#FF8C00",
                    "success": "#32CD32",
                    "error": "#FF4500"
                }
            },
            "download_settings": {
                "max_concurrent_downloads": 1,
                "queue_delay_seconds": 10,
                "default_download_dir": "downloads",
                "auto_retry": True,
                "max_retries": 3,
                "timeout_seconds": 30
            },
            "flash_settings": {
                "default_buffer_size": 1048576,
                "verify_after_copy": True,
                "cleanup_empty_dirs": True,
                "supported_formats": [".wbfs", ".iso", ".rvz"],
                "wbfs_folder": "wbfs"
            },
            "parser_settings": {
                "base_url": "https://vimm.net",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ssl_verify": False,
                "timeout_seconds": 30,
                "cache_images": True,
                "image_cache_dir": "cache/images"
            },
            "database_settings": {
                "file_path": "wii_games.json",
                "auto_save": True,
                "auto_save_interval": 300,
                "backup_count": 5
            },
            "selenium_settings": {
                "download_timeout": 3600,
                "implicit_wait": 10,
                "chrome_options": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage"
                ]
            },
            "logging": {
                "level": "INFO",
                "file": "wii_unified_manager.log",
                "max_size": 10485760,
                "backup_count": 3
            }
        }
    
    def _load_config(self):
        """Загрузка конфигурации из файла"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._merge_config(self.config, file_config)
            except Exception as e:
                print(f"Ошибка при загрузке конфигурации: {e}")
                print("Используется конфигурация по умолчанию")
    
    def _merge_config(self, default: Dict[str, Any], loaded: Dict[str, Any]):
        """Объединение конфигураций"""
        for key, value in loaded.items():
            if key in default:
                if isinstance(default[key], dict) and isinstance(value, dict):
                    self._merge_config(default[key], value)
                else:
                    default[key] = value
            else:
                default[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения конфигурации"""
        keys = key.split('.')
        current = self.config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any):
        """Установка значения конфигурации"""
        keys = key.split('.')
        current = self.config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def save(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении конфигурации: {e}")
    
    def get_ui_colors(self) -> Dict[str, str]:
        """Получение цветов для UI"""
        return self.get('ui_settings.colors', {})
    
    def get_download_settings(self) -> Dict[str, Any]:
        """Получение настроек загрузки"""
        return self.get('download_settings', {})
    
    def get_flash_settings(self) -> Dict[str, Any]:
        """Получение настроек флешки"""
        return self.get('flash_settings', {})
    
    def get_parser_settings(self) -> Dict[str, Any]:
        """Получение настроек парсера"""
        return self.get('parser_settings', {})
    
    def get_database_settings(self) -> Dict[str, Any]:
        """Получение настроек базы данных"""
        return self.get('database_settings', {})
    
    def get_selenium_settings(self) -> Dict[str, Any]:
        """Получение настроек Selenium"""
        return self.get('selenium_settings', {})
    
    def get_logging_settings(self) -> Dict[str, Any]:
        """Получение настроек логирования"""
        return self.get('logging', {})
    
    def create_directories(self):
        """Создание необходимых директорий"""
        dirs_to_create = [
            self.get('download_settings.default_download_dir', 'downloads'),
            self.get('parser_settings.image_cache_dir', 'cache/images'),
            'html_files',
            'backups'
        ]
        
        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def get_app_info(self) -> Dict[str, str]:
        """Получение информации о приложении"""
        return {
            'name': self.get('app_name', 'Wii Unified Manager'),
            'version': self.get('version', '2.0.0'),
            'description': self.get('description', 'Менеджер игр Nintendo Wii')
        }
    
    def reset_to_defaults(self):
        """Сброс настроек к значениям по умолчанию"""
        self.config = self._load_default_config()
        self.save()
    
    def export_config(self, file_path: str):
        """Экспорт конфигурации в файл"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка при экспорте конфигурации: {e}")
            return False
    
    def import_config(self, file_path: str):
        """Импорт конфигурации из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
                self._merge_config(self.config, imported_config)
            return True
        except Exception as e:
            print(f"Ошибка при импорте конфигурации: {e}")
            return False

# Глобальный экземпляр менеджера конфигурации
config_manager = ConfigManager()
