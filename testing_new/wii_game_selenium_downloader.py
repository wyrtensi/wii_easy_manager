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
import requests # For HEAD request
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
        self.progress_callback: Optional[Callable[[int, int, float, str], None]] = None # bytes, total_bytes, speed, eta
        self.should_stop = False # Internal flag, primarily set by stop_download()

    def setup_driver(self):
        """Настройка Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        # chrome_options.add_argument("--headless") # Optional: run headless
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome WebDriver успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации Chrome WebDriver: {e}")
            self.driver = None # Ensure driver is None on failure
            return False

    def cleanup_downloads(self):
        """Очистка файлов .crdownload из папки загрузок."""
        try:
            for file in self.download_dir.glob("*.crdownload"):
                if file.is_file():
                    file.unlink()
            logger.info("Файлы .crdownload очищены из папки загрузок.")
        except Exception as e:
            logger.warning(f"Ошибка при очистке файлов .crdownload: {e}")

    def try_start_download(self, game_url: str) -> bool:
        """Попытка начать загрузку игры."""
        try:
            if not self.driver:
                logger.error("WebDriver не инициализирован.")
                return False

            self.driver.get(game_url)
            # Wait for page to load, specifically for the download button
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//form[@id='dl_form']/button"))
            )

            button = self.driver.find_element(By.XPATH, "//form[@id='dl_form']/button")
            button.click()
            logger.info("Кнопка скачивания нажата.")

            # Wait for .crdownload file to appear
            time.sleep(1) # Initial small delay
            for _ in range(15): # Wait up to 15 seconds for .crdownload
                if self.should_stop: return False
                files = list(self.download_dir.glob("*.crdownload"))
                if files:
                    logger.info(f"Загрузка началась: {files[0].name}")
                    return True
                time.sleep(1)

            logger.warning(".crdownload файл не появился после нажатия кнопки.")
            return False

        except Exception as e:
            logger.error(f"Ошибка при попытке начать загрузку ({game_url}): {e}")
            return False

    def monitor_download_progress(self, filepath: Path, initial_total_size_gb: float = 4.0, should_stop_external_check: Optional[Callable[[], bool]] = None):
        logger.info(f"Starting to monitor {filepath.name}. External stop check: {should_stop_external_check is not None}")
        last_size = 0
        stall_count = 0
        estimated_total_bytes = int(initial_total_size_gb * (1024**3))
        start_time = time.time()
        last_progress_call_time = time.time()

        while filepath.exists(): # Loop while .crdownload file exists
            time.sleep(0.25)

            if self.should_stop:
                logger.info(f"Internal stop signal for {filepath.name}.")
                break
            if should_stop_external_check and should_stop_external_check():
                logger.info(f"External stop signal for {filepath.name}.")
                self.stop_download() # Trigger internal stop
                break

            try:
                current_size = filepath.stat().st_size
                now = time.time()

                if current_size > last_size :
                    stall_count = 0
                    if self.progress_callback and (now - last_progress_call_time >= 1.0):
                        elapsed_time_total = now - start_time
                        speed_bps = current_size / elapsed_time_total if elapsed_time_total > 0 else 0
                        speed_mbps = speed_bps / (1024**2)

                        eta_seconds = float('inf')
                        if speed_bps > 0 and estimated_total_bytes > current_size :
                            eta_seconds = (estimated_total_bytes - current_size) / speed_bps

                        eta_str = self.format_time(eta_seconds)
                        self.progress_callback(current_size, estimated_total_bytes, speed_mbps, eta_str)
                        last_progress_call_time = now
                    last_size = current_size
                elif current_size == last_size:
                    stall_count += 1
                    if stall_count * 0.25 > 120:  # Stalled for 120 seconds (2 minutes)
                        logger.warning(f"Download {filepath.name} stalled for 120 seconds. Stopping.")
                        self.stop_download()
                        break
                else:
                    logger.warning(f"File size decreased for {filepath.name}. current: {current_size}, last: {last_size}")
                    last_size = current_size

            except FileNotFoundError:
                logger.info(f"File {filepath.name} disappeared during monitoring (completed or cancelled).")
                break # Exit loop if file is gone
            except Exception as e:
                logger.error(f"Error monitoring {filepath.name}: {e}")
                break

        logger.info(f"Monitoring finished for {filepath.name}. should_stop={self.should_stop}")

        # Final progress update if download seems completed
        if self.progress_callback:
            final_file_name = filepath.stem # Name without .crdownload
            final_file = self.download_dir / final_file_name
            if final_file.exists() and not self.should_stop : # If final file exists and not stopped
                final_size = final_file.stat().st_size
                logger.info(f"Download completed for {final_file_name}, final size {final_size}. Emitting 100%.")
                self.progress_callback(final_size, final_size, 0, "0 сек")
            elif self.should_stop: # If stopped
                 logger.info(f"Download was stopped for {filepath.name}. Emitting last known progress or 0%.")
                 self.progress_callback(last_size, estimated_total_bytes, 0, "Отменено")
            else: # .crdownload gone but no final file, and not explicitly stopped (could be error)
                 logger.info(f"Download of {filepath.name} likely failed or was externally removed. Emitting last known progress.")
                 self.progress_callback(last_size, estimated_total_bytes, 0, "Ошибка")


    def format_time(self, seconds: float) -> str:
        if seconds == float('inf') or seconds < 0:
            return "..."
        if seconds < 60:
            return f"{int(seconds)} сек"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes} мин {secs} сек"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours} ч {minutes} мин"

    def download_game(self, game_url: str, game_title: str,
                     progress_callback: Optional[Callable[[int, int, float, str], None]] = None, # Corrected signature
                     should_stop_external_check: Optional[Callable[[], bool]] = None) -> bool:
        self.should_stop = False
        self.progress_callback = progress_callback

        estimated_size_gb = 4.0
        logger.info(f"Preparing to download {game_title} from {game_url}")

        if not self.setup_driver():
            if self.should_stop: logger.info("Driver setup aborted by stop request.")
            return False

        max_attempts = 3
        success = False
        for attempt in range(max_attempts):
            if self.should_stop or (should_stop_external_check and should_stop_external_check()):
                logger.info(f"Download attempt {attempt + 1} for {game_title} aborted by stop signal.")
                break

            logger.info(f"Download attempt {attempt + 1}/{max_attempts} for {game_title}")

            if self.try_start_download(game_url):
                crdownload_files = list(self.download_dir.glob("*.crdownload"))
                if crdownload_files:
                    filepath = crdownload_files[0]
                    logger.info(f"Monitoring {filepath.name} for {game_title}")

                    self.monitor_download_progress(filepath, estimated_size_gb, should_stop_external_check)

                    if self.should_stop:
                        logger.info(f"Download of {game_title} was stopped.")
                        success = False
                        break

                    final_filename = filepath.stem
                    final_filepath = self.download_dir / final_filename
                    if final_filepath.exists():
                        logger.info(f"Download completed successfully: {final_filename}")
                        success = True
                        break
                    else:
                        logger.warning(f".crdownload for {game_title} disappeared, but final file not found. Assuming failure or cancellation.")
                        success = False
                else:
                    logger.warning(f"try_start_download succeeded for {game_title} but no .crdownload file found immediately after.")
                    success = False
            else:
                success = False

            if not success and attempt < max_attempts - 1 and not self.should_stop:
                logger.info(f"Attempt {attempt + 1} failed for {game_title}. Retrying after delay...")
                if self.driver:
                    try:
                        self.driver.get("chrome://version")
                        time.sleep(2)
                    except Exception as e_nav:
                        logger.warning(f"Could not navigate away during retry prep: {e_nav}")
                else:
                    if not self.setup_driver(): break
                time.sleep(5)
            elif self.should_stop:
                break

        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error quitting driver: {e}")
            finally:
                self.driver = None

        logger.info(f"Download process for {game_title} finished. Success: {success}, Internal stop flag: {self.should_stop}")
        return success

    def stop_download(self):
        logger.info("stop_download called. Setting internal stop flag.")
        self.should_stop = True
        if self.driver:
            logger.info("Attempting to close WebDriver to halt download.")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error trying to quit driver in stop_download: {e}")
            finally:
                self.driver = None
        else:
            logger.info("No active WebDriver to stop.")

    def get_downloaded_files(self) -> list[Path]:
        """Получение списка скачанных (не .crdownload) файлов в папке загрузок."""
        try:
            return [f for f in self.download_dir.glob("*")
                   if f.is_file() and not f.name.endswith('.crdownload')]
        except Exception as e:
            logger.error(f"Error getting downloaded files: {e}")
            return []

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    downloader = WiiGameSeleniumDownloader(download_dir="test_selenium_downloads")
    test_game_url = "https://vimm.net/vault/17830"
    test_game_title = "Animal Crossing City Folk EUR"

    def my_progress_callback(current_bytes, total_bytes, speed_mbps, eta_str):
        percent = int((current_bytes/total_bytes)*100) if total_bytes > 0 else 0
        print(f"Progress: {percent}% - {current_bytes/1024**2:.2f}MB / {total_bytes/1024**2:.2f}MB - Speed: {speed_mbps:.2f} MB/s - ETA: {eta_str}")

    print(f"Starting test download for {test_game_title}...")

    stop_flag = False
    def external_stop_check():
        return stop_flag

    success = downloader.download_game(test_game_url, test_game_title, my_progress_callback, external_stop_check)

    if success:
        print(f"Test download SUCCEEDED for {test_game_title}.")
        files = downloader.get_downloaded_files()
        print("Downloaded files:", [f.name for f in files])
    else:
        print(f"Test download FAILED or was CANCELLED for {test_game_title}.")

    print("Test finished.")
