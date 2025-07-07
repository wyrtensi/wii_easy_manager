@echo off
echo Wii Game Browser - Launcher
echo ============================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: Python не найден!
    echo Пожалуйста, установите Python 3.7 или новее
    pause
    exit /b 1
)

echo Python найден
echo.

REM Проверяем зависимости
echo Проверка зависимостей...
python -c "import PySide6" >nul 2>&1
if %errorlevel% neq 0 (
    echo Устанавливаем зависимости...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Ошибка при установке зависимостей!
        pause
        exit /b 1
    )
)

echo Запускаем Wii Game Browser...
echo.
python wii_game_browser.py

if %errorlevel% neq 0 (
    echo.
    echo Произошла ошибка при запуске приложения
    pause
)
