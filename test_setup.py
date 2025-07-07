#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки Wii Unified Manager
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Тест импортов"""
    print("🔍 Проверка импортов...")
    
    try:
        import PySide6
        print("✅ PySide6 найден")
    except ImportError as e:
        print(f"❌ PySide6 не найден: {e}")
        return False
    
    try:
        import requests
        print("✅ requests найден")
    except ImportError as e:
        print(f"❌ requests не найден: {e}")
        return False
    
    try:
        import bs4
        print("✅ beautifulsoup4 найден")
    except ImportError as e:
        print(f"❌ beautifulsoup4 не найден: {e}")
        return False
    
    try:
        import selenium
        print("✅ selenium найден")
    except ImportError as e:
        print(f"❌ selenium не найден: {e}")
        return False
    
    try:
        import psutil
        print("✅ psutil найден")
    except ImportError as e:
        print(f"❌ psutil не найден: {e}")
        return False
    
    return True

def test_modules():
    """Тест наших модулей"""
    print("\n🔍 Проверка модулей...")
    
    try:
        from wii_game_parser import WiiGameParser, WiiGameDatabase, WiiGame
        print("✅ wii_game_parser найден")
    except ImportError as e:
        print(f"❌ wii_game_parser не найден: {e}")
        return False
    
    try:
        from wii_game_selenium_downloader import WiiGameSeleniumDownloader
        print("✅ wii_game_selenium_downloader найден")
    except ImportError as e:
        print(f"❌ wii_game_selenium_downloader не найден: {e}")
        return False
    
    try:
        from wii_download_manager.models.enhanced_drive import EnhancedDrive
        print("✅ enhanced_drive найден")
    except ImportError as e:
        print(f"❌ enhanced_drive не найден: {e}")
        return False
    
    try:
        from wii_download_manager.models.game import Game
        print("✅ game model найден")
    except ImportError as e:
        print(f"❌ game model не найден: {e}")
        return False
    
    return True

def test_directories():
    """Тест директорий"""
    print("\n🔍 Проверка директорий...")
    
    current_dir = Path.cwd()
    print(f"📁 Текущая директория: {current_dir}")
    
    downloads_dir = current_dir / "downloads"
    if not downloads_dir.exists():
        downloads_dir.mkdir()
        print("✅ Создана папка downloads")
    else:
        print("✅ Папка downloads существует")
    
    html_dir = current_dir / "html_files"
    if not html_dir.exists():
        html_dir.mkdir()
        print("✅ Создана папка html_files")
    else:
        print("✅ Папка html_files существует")
    
    return True

def test_drives():
    """Тест поиска флешек"""
    print("\n🔍 Проверка флешек...")
    
    try:
        from wii_download_manager.models.enhanced_drive import EnhancedDrive
        drives = EnhancedDrive.get_drives()
        
        if drives:
            print(f"✅ Найдено {len(drives)} съемных дисков:")
            for drive in drives:
                print(f"  💾 {drive.name} - {drive.available_space}/{drive.total_space} GB")
        else:
            print("⚠️ Съемные диски не найдены")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при поиске дисков: {e}")
        return False

def test_parser():
    """Тест парсера"""
    print("\n🔍 Проверка парсера...")
    
    try:
        from wii_game_parser import WiiGameParser, WiiGameDatabase
        
        parser = WiiGameParser()
        database = WiiGameDatabase()
        
        print("✅ Парсер и база данных созданы")
        
        # Проверяем существующие HTML файлы
        html_files = list(Path.cwd().glob("*.html"))
        if html_files:
            print(f"✅ Найдено {len(html_files)} HTML файлов")
            for file in html_files:
                print(f"  📄 {file.name}")
        else:
            print("⚠️ HTML файлы не найдены")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании парсера: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🎮 Тестирование Wii Unified Manager")
    print("=" * 50)
    
    success = True
    
    # Тестируем импорты
    if not test_imports():
        success = False
    
    # Тестируем модули
    if not test_modules():
        success = False
    
    # Тестируем директории
    if not test_directories():
        success = False
    
    # Тестируем флешки
    if not test_drives():
        success = False
    
    # Тестируем парсер
    if not test_parser():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Все тесты пройдены!")
        print("🚀 Можно запускать wii_unified_manager.py")
    else:
        print("❌ Некоторые тесты не пройдены")
        print("📋 Проверьте зависимости: pip install -r requirements.txt")
    
    input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()
