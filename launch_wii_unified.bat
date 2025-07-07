@echo off
chcp 65001 >nul
title 🎮 Wii Unified Manager - Launcher

echo.
echo ╔════════════════════════════════════════════════════════════════════════════════╗
echo ║                           🎮 Wii Unified Manager                               ║
echo ║                        Красивый менеджер игр Nintendo Wii                      ║
echo ╚════════════════════════════════════════════════════════════════════════════════╝
echo.
echo 🎯 Возможности:
echo   • 🔍 Поиск игр онлайн и локально
echo   • 📥 Умная система загрузок с очередью
echo   • 💾 Управление играми на флешке
echo   • 🎨 Красивый интерфейс в стиле Wii
echo   • 🖼️ Большие карточки игр с изображениями
echo.

REM Проверка Python
echo [1/5] 🐍 Проверка Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ❌ Python не найден!
    echo   📥 Скачайте Python 3.8+ с https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   ✅ Python %PYTHON_VERSION% найден

REM Проверка зависимостей
echo.
echo [2/5] 📦 Проверка зависимостей...
python -c "import PySide6, requests, bs4, selenium, psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ Некоторые зависимости не найдены, устанавливаем...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo   ❌ Ошибка при установке зависимостей!
        echo   💡 Попробуйте запустить как администратор
        pause
        exit /b 1
    )
    echo   ✅ Зависимости установлены
) else (
    echo   ✅ Все зависимости найдены
)

REM Проверка Chrome
echo.
echo [3/5] 🌐 Проверка Chrome...
where chrome >nul 2>&1
if %errorlevel% neq 0 (
    where "C:\Program Files\Google\Chrome\Application\chrome.exe" >nul 2>&1
    if %errorlevel% neq 0 (
        where "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" >nul 2>&1
        if %errorlevel% neq 0 (
            echo   ⚠️ Chrome не найден - загрузка игр может не работать
            echo   💡 Установите Google Chrome для полного функционала
        ) else (
            echo   ✅ Chrome найден (x86)
        )
    ) else (
        echo   ✅ Chrome найден (x64)
    )
) else (
    echo   ✅ Chrome найден
)

REM Подготовка среды
echo.
echo [4/5] 📁 Подготовка среды...
if not exist "downloads" mkdir downloads
if not exist "html_files" mkdir html_files
if not exist "cache" mkdir cache
if not exist "cache\images" mkdir cache\images
if not exist "backups" mkdir backups
echo   ✅ Папки подготовлены

REM Проверка модулей
echo.
echo [5/5] 🔧 Проверка модулей...
python test_setup.py >nul 2>&1
if %errorlevel% neq 0 (
    echo   ⚠️ Некоторые модули требуют внимания
    echo   💡 Запустите test_setup.py для диагностики
) else (
    echo   ✅ Все модули готовы
)

echo.
echo ╔════════════════════════════════════════════════════════════════════════════════╗
echo ║                              🚀 ЗАПУСК ПРИЛОЖЕНИЯ                             ║
echo ╚════════════════════════════════════════════════════════════════════════════════╝
echo.

REM Запуск приложения
python wii_unified_manager.py

REM Обработка результата
echo.
if %errorlevel% equ 0 (
    echo ✅ Приложение закрыто корректно
) else (
    echo ❌ Приложение завершилось с ошибкой (код: %errorlevel%)
    echo.
    echo 🔧 Возможные решения:
    echo   • Запустите как администратор
    echo   • Проверьте интернет-соединение
    echo   • Обновите драйверы
    echo   • Перезагрузите компьютер
    echo.
    echo 📋 Для диагностики запустите: python test_setup.py
    echo.
    pause
)

echo.
echo 👋 Спасибо за использование Wii Unified Manager!
timeout /t 3 /nobreak >nul
