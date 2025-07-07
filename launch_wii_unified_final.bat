@echo off
chcp 65001 >nul
title 🎮 Wii Unified Manager - Launcher

echo.
echo ═══════════════════════════════════════════════════════════════
echo           🎮 Wii Unified Manager - Финальная версия
echo ═══════════════════════════════════════════════════════════════
echo.
echo 🚀 Запуск современного менеджера игр Nintendo Wii...
echo.

echo 🔍 Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Установите Python 3.8+ и повторите попытку.
    pause
    exit /b 1
)
echo ✅ Python найден

echo.
echo 🔍 Проверка зависимостей...
python -c "import PySide6; print('✅ PySide6 найден')" 2>nul || (echo ❌ PySide6 не найден & echo 📦 Устанавливаем зависимости... & pip install -r requirements.txt)
python -c "import requests; print('✅ requests найден')" 2>nul || (echo ❌ requests не найден & pip install requests)
python -c "import beautifulsoup4; print('✅ beautifulsoup4 найден')" 2>nul || (echo ❌ beautifulsoup4 не найден & pip install beautifulsoup4)
python -c "import selenium; print('✅ selenium найден')" 2>nul || (echo ❌ selenium не найден & pip install selenium)

echo.
echo 🔍 Проверка файлов проекта...
if not exist "wii_unified_manager.py" (
    echo ❌ Основной файл не найден!
    pause
    exit /b 1
)
echo ✅ Основной файл найден

if not exist "wii_game_parser.py" (
    echo ❌ Парсер не найден!
    pause
    exit /b 1
)
echo ✅ Парсер найден

if not exist "downloads" mkdir downloads
echo ✅ Папка downloads готова

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                    🎮 НОВЫЕ ВОЗМОЖНОСТИ                      ║
echo ╠═══════════════════════════════════════════════════════════════╣
echo ║ ✨ Светлый современный дизайн в стиле Nintendo                ║
echo ║ 🔍 Упрощенный поиск без лишних фильтров                      ║
echo ║ 📋 Полные карточки игр с детальной информацией                ║
echo ║ 🖼️ Исправлена загрузка изображений обложек                   ║
echo ║ 📥 Детальный прогресс загрузки (скорость, время, размер)     ║
echo ║ 💾 Менеджер игр: скачанные + на флешке                       ║
echo ║ 🔎 Поиск среди ваших игр                                      ║
echo ║ 🗑️ Исправлено удаление игр                                    ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

echo 🚀 Запускаем Wii Unified Manager...
echo.

python wii_unified_manager.py

echo.
echo 👋 Спасибо за использование Wii Unified Manager!
echo 💡 Для повторного запуска просто запустите этот файл снова.
echo.
pause
