#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для загрузки игр Wii с использованием Selenium
Основан на рабочем test.py скрипте
"""

import os
import time
import logging
import threading
from typing import Optional, Callable
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class WiiGameSeleniumDownloader:
    """Класс для загрузки игр Wii с использованием Selenium"""

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.cancel_url = "https://dl3.vimm.net/download/cancel.php"
        self.driver = None
        self.download_thread = None # This seems unused in this class context
        self.progress_callback: Optional[Callable[..., None]] = None
        self.external_stop_callback: Optional[Callable[[], bool]] = None # For external stop signal
        self.should_stop = False # Internal stop signal

    def setup_driver(self):
        """Настройка Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # chrome_options.add_argument("--headless") # Consider adding for non-UI downloads

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome WebDriver успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации Chrome WebDriver: {e}")
            # Attempt to provide more specific feedback if possible
            if "chromedriver executable needs to be in PATH" in str(e).lower():
                logger.error("ChromeDriver не найден. Убедитесь, что он установлен и находится в системном PATH.")
            return False

    def cleanup_downloads(self):
        """Очистка папки загрузок ПЕРЕД новой загрузкой"""
        try:
            for file in self.download_dir.glob("*.crdownload"): # Remove partial downloads
                file.unlink()
            # Potentially remove other files if a strict cleanup is needed,
            # but this might delete user's other completed downloads if they use the same folder.
            # For now, only .crdownload files.
            logger.info("Частичные загрузки (.crdownload) очищены")
        except Exception as e:
            logger.warning(f"Ошибка при очистке частичных загрузок: {e}")

    def try_start_download(self, game_url: str) -> bool:
        """Попытка начать загрузку игры"""
        try:
            if not self.driver:
                logger.error("Драйвер не инициализирован перед попыткой загрузки.")
                return False

            self.driver.get(game_url)
            # Wait for page to load and potentially for dynamic elements
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2) # Additional small delay

            # Ищем кнопку скачивания
            try:
                # More robust XPath, assuming the button is within a form with id 'dl_form'
                button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//form[@id='dl_form']/button[@type='submit'] | //form[@id='dl_form']/input[@type='submit']"))
                )
                button.click()
                logger.info("Кнопка скачивания нажата")
            except Exception as e:
                logger.warning(f"Не удалось найти или нажать кнопку скачивания: {e}")
                # self.driver.save_screenshot(str(self.download_dir / "debug_screenshot_button_not_found.png"))
                return False

            # Ждем начала загрузки до 20 секунд (увеличено)
            for _ in range(20):
                if self.should_stop or (self.external_stop_callback and self.external_stop_callback()):
                    logger.info("Получен сигнал остановки во время ожидания начала загрузки.")
                    return False

                files = list(self.download_dir.glob("*.crdownload"))
                if files:
                    logger.info(f"Загрузка началась: {files[0].name}")
                    return True
                time.sleep(1)

            logger.warning("Файл .crdownload не появился после нажатия кнопки.")
            return False

        except Exception as e:
            logger.error(f"Ошибка при попытке начать загрузку: {e}")
            return False

    def monitor_download_progress(self, filepath: Path, game_total_size_bytes: Optional[int] = None):
        """
        Мониторинг прогресса загрузки.
        game_total_size_bytes: Опциональный общий размер игры в байтах для расчета процента.
        """
        last_size = 0
        stall_count = 0
        start_time = time.time()

        logger.info(f"Мониторинг файла: {filepath}")

        while filepath.exists():
            if self.should_stop or (self.external_stop_callback and self.external_stop_callback()):
                logger.info("Сигнал остановки получен во время мониторинга.")
                break
            try:
                current_size = filepath.stat().st_size

                if current_size > last_size:
                    elapsed_time = time.time() - start_time
                    speed = (current_size - last_size) / (elapsed_time if elapsed_time > 0 else 1) # bytes/sec
                    start_time = time.time() # Reset start_time for next speed calculation chunk
                    last_size_for_speed_calc = current_size

                    if self.progress_callback:
                        percent = 0
                        if game_total_size_bytes and game_total_size_bytes > 0:
                            percent = int((current_size / game_total_size_bytes) * 100)

                        eta_str = "N/A"
                        if speed > 0 and game_total_size_bytes:
                            remaining_bytes = game_total_size_bytes - current_size
                            if remaining_bytes > 0:
                                eta_seconds = remaining_bytes / speed
                                # format eta_seconds into hh:mm:ss or mm:ss
                                if eta_seconds > 3600:
                                    eta_str = time.strftime('%Hч %Mм %Sс', time.gmtime(eta_seconds))
                                else:
                                    eta_str = time.strftime('%Mм %Sс', time.gmtime(eta_seconds))

                        # Call progress callback with downloaded bytes and total bytes
                        # DownloadThread expects callback(downloaded: int, total: int)
                        if self.progress_callback:
                            # If we don't know total size, use 0 to indicate indeterminate progress
                            total_bytes = game_total_size_bytes if game_total_size_bytes else 0
                            self.progress_callback(current_size, total_bytes)

                    last_size = current_size
                    stall_count = 0
                elif current_size == last_size : # File size hasn't changed
                    stall_count += 1
                    if stall_count > 60:  # 60 секунд без изменений
                        logger.warning(f"Загрузка файла {filepath.name} остановилась на {current_size} байт.")
                        # Consider this a failure or attempt recovery
                        break
                else: # File size decreased or other issue
                    logger.warning(f"Размер файла {filepath.name} уменьшился, что странно. Текущий: {current_size}, Предыдущий: {last_size}")
                    break


                time.sleep(1)

            except FileNotFoundError:
                logger.info(f"Файл {filepath.name} больше не существует. Возможно, загрузка завершена или отменена.")
                break
            except Exception as e:
                logger.error(f"Ошибка при мониторинге загрузки {filepath.name}: {e}")
                break

        if not (self.should_stop or (self.external_stop_callback and self.external_stop_callback())):
            if not filepath.exists(): # If loop exited due to file not existing, and not due to stop signal
                 # Check if the final file (without .crdownload) exists
                final_name = filepath.stem
                final_path = self.download_dir / final_name
                if final_path.exists():
                    logger.info(f"Мониторинг завершен: файл {filepath.name} переименован в {final_name}.")
                    if self.progress_callback and game_total_size_bytes: # Send 100%
                        self.progress_callback(game_total_size_bytes, game_total_size_bytes)
                else:
                    logger.warning(f"Мониторинг завершен: файл {filepath.name} исчез, но финальный файл не найден.")
            # else: file still exists, but loop terminated (e.g. stall)


    def download_game(self, game_url: str, game_title: str,
                     game_id: Optional[str] = None,
                     progress_callback: Optional[Callable[..., None]] = None,
                     stop_callback: Optional[Callable[[], bool]] = None,
                     total_size_bytes: Optional[int] = None) -> bool:
        """
        Загрузка игры

        Args:
            game_url: URL страницы игры
            game_title: Название игры для логов
            game_id: ID игры (опционально, для информации)
            progress_callback: Функция обратного вызова для отображения прогресса
                               (ожидает: percent, speed_MBs, eta_string)
            stop_callback: Функция обратного вызова для проверки сигнала остановки

        Returns:
            True если загрузка успешна, False иначе
        """
        self.should_stop = False  # Reset internal stop flag
        self.progress_callback = progress_callback
        self.external_stop_callback = stop_callback

        # Размер файла, если известен, используется для расчета процента
        game_total_size_bytes = total_size_bytes
        logger.info(f"Запрос на загрузку игры: {game_title} (ID: {game_id}), URL: {game_url}")

        try:
            if not self.setup_driver():
                return False

            self.cleanup_downloads() # Clean up before starting

            logger.info(f"Попытка загрузить игру: {game_title}")

            max_attempts = 3 # Reduced max_attempts for faster failure if issues persist
            for attempt in range(max_attempts):
                if self.should_stop or (self.external_stop_callback and self.external_stop_callback()):
                    logger.info("Загрузка отменена перед попыткой.")
                    break

                logger.info(f"Попытка {attempt + 1} из {max_attempts}")

                if self.try_start_download(game_url):
                    crdownload_files = list(self.download_dir.glob("*.crdownload"))
                    if crdownload_files:
                        filepath = crdownload_files[0]
                        logger.info(f"Файл загрузки: {filepath}")

                        # For now, we don't have actual total size.
                        # The progress_callback in DownloadThread expects (percent, speed, eta)
                        # monitor_download_progress needs to be adapted to provide this.
                        self.monitor_download_progress(filepath, game_total_size_bytes)

                        # Check conditions after monitor_download_progress finishes
                        if self.should_stop or (self.external_stop_callback and self.external_stop_callback()):
                            logger.info(f"Загрузка {game_title} остановлена.")
                            # Ensure .crdownload is removed if stopped
                            if filepath.exists():
                                try: filepath.unlink()
                                except OSError as e: logger.error(f"Не удалось удалить {filepath}: {e}")
                            return False

                        # Check if the download completed successfully (file renamed, no .crdownload)
                        final_filename_stem = filepath.stem # Original name without .crdownload
                        final_filepath = self.download_dir / final_filename_stem

                        if final_filepath.exists() and not filepath.exists():
                            logger.info(f"Загрузка успешно завершена: {final_filepath.name}")
                            # Send final progress update if callback exists
                            if self.progress_callback:
                                final_size = final_filepath.stat().st_size if final_filepath.exists() else 0
                                self.progress_callback(final_size, final_size)
                            return True
                        else:
                            logger.warning(f"Загрузка {game_title} не завершилась корректно. Файл: {final_filepath.name}, существует: {final_filepath.exists()}, .crdownload остался: {filepath.exists()}")
                    else:
                        logger.warning(f"Файл .crdownload не найден после try_start_download для {game_title}, хотя должен был.")

                if attempt < max_attempts - 1:
                    logger.info(f"Попытка {attempt + 1} не удалась для {game_title}. Ожидание перед следующей попыткой...")
                    time.sleep(5) # Wait before retrying
                    # Consider re-initializing driver or further reset steps if needed
                    if self.driver: # Try to cancel any pending browser state
                        try: self.driver.get("chrome://downloads"); time.sleep(1); self.driver.get(self.cancel_url); time.sleep(1)
                        except Exception as e: logger.warning(f"Ошибка при попытке сброса состояния браузера: {e}")
                else: # Last attempt failed
                     logger.error(f"Не удалось загрузить игру {game_title} после {max_attempts} попыток.")
                     # Make sure to clean up .crdownload if it's the last attempt and failed
                     crdownload_files = list(self.download_dir.glob("*.crdownload"))
                     for f in crdownload_files:
                         try: f.unlink(); logger.info(f"Удален оставшийся .crdownload файл: {f.name}")
                         except OSError as e: logger.error(f"Не удалось удалить {f.name}: {e}")


            return False # All attempts failed or was stopped

        except Exception as e:
            logger.error(f"Критическая ошибка при загрузке игры {game_title}: {e}", exc_info=True)
            return False

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info(f"WebDriver для {game_title} закрыт.")
                except Exception as e:
                    logger.error(f"Ошибка при закрытии WebDriver для {game_title}: {e}")
                self.driver = None
            self.external_stop_callback = None # Clear callback
            self.progress_callback = None      # Clear callback

    def stop_download(self):
        """Остановка текущей загрузки (внутренний флаг + попытка закрыть драйвер)"""
        logger.info("Получен вызов stop_download().")
        self.should_stop = True

        # WebDriver might be in use by a thread, quitting it here might be abrupt.
        # The thread itself should check self.should_stop and self.external_stop_callback.
        # However, if a quick stop is needed:
        if self.driver:
            logger.info("Пытаюсь закрыть WebDriver для остановки загрузки...")
            try:
                # self.driver.get(self.cancel_url) # May not be effective if download is browser-native
                # time.sleep(1)
                self.driver.quit()
                self.driver = None
                logger.info("WebDriver закрыт для остановки.")
            except Exception as e:
                logger.error(f"Ошибка при закрытии WebDriver во время остановки: {e}")

        logger.info("Сигнал остановки загрузки установлен.")

    def get_downloaded_files(self) -> list[Path]:
        """Получение списка скачанных файлов (не .crdownload)"""
        try:
            return [f for f in self.download_dir.glob("*")
                   if f.is_file() and not f.name.endswith('.crdownload')]
        except Exception as e:
            logger.error(f"Ошибка при получении списка скачанных файлов: {e}")
            return []

if __name__ == '__main__':
    # Basic test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    downloader = WiiGameSeleniumDownloader(download_dir="test_downloads")

    # Example: Super Mario Galaxy URL (replace with a real one if this is invalid)
    # Note: Vimm's Lair download URLs are often dynamic or require session cookies.
    # This test might fail if the URL isn't directly downloadable or if CAPTCHAs appear.
    test_game_url = "https://vimm.net/vault/18198" # This is a page URL, not direct download
    test_game_title = "Super Mario Galaxy (Test)"
    test_game_id = "18198"

    def sample_progress(percent, speed_mbs, eta_str):
        logger.info(f"Прогресс загрузки: {percent}% - {speed_mbs:.2f} MB/s - ETA: {eta_str}")

    stop_event = threading.Event()

    def stop_condition():
        return stop_event.is_set()

    # To test stop, run this in a thread and set stop_event after some time
    # threading.Timer(15, stop_event.set).start() # Stop after 15 seconds

    logger.info(f"Начало тестовой загрузки для: {test_game_title}")
    success = downloader.download_game(test_game_url, test_game_title, test_game_id, sample_progress, stop_condition, None)

    if success:
        logger.info(f"Тестовая загрузка '{test_game_title}' завершена успешно.")
        files = downloader.get_downloaded_files()
        logger.info(f"Скачанные файлы: {files}")
    else:
        logger.info(f"Тестовая загрузка '{test_game_title}' не удалась или была отменена.")

    # Cleanup test_downloads directory
    # import shutil
    # if Path("test_downloads").exists():
    #     shutil.rmtree("test_downloads")
    #     logger.info("Папка test_downloads удалена.")
