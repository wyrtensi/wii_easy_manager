@echo off
title Wii Unified Manager - Launcher
echo.
echo ========================================
echo    Wii Unified Manager - Launcher
echo ========================================
echo.
echo Красивый менеджер игр Nintendo Wii
echo Поиск, загрузка и управление играми
echo.

REM Проверяем наличие Python
echo [1/4] Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ОШИБКА: Python не найден!
    echo.
    echo Пожалуйста, установите Python 3.8 или новее:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

python -c "import sys; print(f'✅ Python {sys.version.split()[0]} найден')"
echo.

REM Проверяем основные зависимости
echo [2/4] Проверка зависимостей...
python -c "import PySide6" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  PySide6 не найден, устанавливаем зависимости...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ Ошибка при установке зависимостей!
        echo.
        echo Попробуйте установить вручную:
        echo pip install PySide6 requests beautifulsoup4 lxml selenium tqdm psutil
        echo.
        pause
        exit /b 1
    )
    echo ✅ Зависимости установлены
) else (
    echo ✅ Зависимости найдены
)
echo.

REM Проверяем наличие Chrome для Selenium
echo [3/4] Проверка Chrome...
where chrome >nul 2>&1
if %errorlevel% neq 0 (
    where "C:\Program Files\Google\Chrome\Application\chrome.exe" >nul 2>&1
    if %errorlevel% neq 0 (
        where "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" >nul 2>&1
        if %errorlevel% neq 0 (
            echo ⚠️  Chrome не найден
            echo Для загрузки игр рекомендуется установить Google Chrome
            echo.
        ) else (
            echo ✅ Chrome найден
        )
    ) else (
        echo ✅ Chrome найден
    )
) else (
    echo ✅ Chrome найден
)
echo.

REM Создаем папки если не существуют
echo [4/4] Подготовка папок...
if not exist "downloads" mkdir downloads
if not exist "html_files" mkdir html_files
echo ✅ Папки готовы
echo.

REM Запускаем приложение
echo 🚀 Запуск Wii Unified Manager...
echo.
echo ========================================
echo.

python wii_unified_manager.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Произошла ошибка при запуске приложения
    echo.
    echo Код ошибки: %errorlevel%
    echo.
    echo Попробуйте:
    echo 1. Перезапустить как администратор
    echo 2. Проверить наличие всех зависимостей
    echo 3. Обновить драйверы
    echo.
    pause
) else (
    echo.
    echo ✅ Приложение закрыто успешно
)
