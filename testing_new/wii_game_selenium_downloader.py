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
        self.download_thread = None
        self.progress_callback = None
        self.should_stop = False
        
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
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome WebDriver успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации Chrome WebDriver: {e}")
            return False
    
    def cleanup_downloads(self):
        """Очистка папки загрузок"""
        try:
            for file in self.download_dir.glob("*"):
                if file.is_file():
                    file.unlink()
            logger.info("Папка загрузок очищена")
        except Exception as e:
            logger.warning(f"Ошибка при очистке папки загрузок: {e}")
    
    def try_start_download(self, game_url: str) -> bool:
        """Попытка начать загрузку игры"""
        try:
            if not self.driver:
                return False
                
            self.driver.get(game_url)
            time.sleep(2)
            
            # Ищем кнопку скачивания
            try:
                button = self.driver.find_element(By.XPATH, "//form[@id='dl_form']/button")
                button.click()
                logger.info("Кнопка скачивания нажата")
            except Exception as e:
                logger.warning(f"Не удалось найти кнопку скачивания: {e}")
                return False
            
            # Ждем начала загрузки до 10 секунд
            for _ in range(10):
                if self.should_stop:
                    return False
                    
                files = list(self.download_dir.glob("*.crdownload"))
                if files:
                    logger.info(f"Загрузка началась: {files[0].name}")
                    return True
                time.sleep(1)
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при попытке начать загрузку: {e}")
            return False
    
    def monitor_download_progress(self, filepath: Path, total_size_bytes: Optional[int] = None):
        """Мониторинг прогресса загрузки"""
        last_size = 0
        stall_count = 0
        
        while filepath.exists() and not self.should_stop:
            try:
                current_size = filepath.stat().st_size
                
                if current_size > last_size:
                    # Загрузка идет
                    if self.progress_callback:
                        downloaded = current_size
                        total = total_size_bytes if total_size_bytes else 0
                        self.progress_callback(downloaded, total)
                    
                    last_size = current_size
                    stall_count = 0
                else:
                    # Загрузка остановилась
                    stall_count += 1
                    if stall_count > 30:  # 30 секунд без изменений
                        logger.warning("Загрузка остановилась, возможно нужно перезапустить")
                        break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка при мониторинге загрузки: {e}")
                break
    
    def download_game(self, game_url: str, game_title: str,
                     progress_callback: Optional[Callable[[float, float], None]] = None,
                     total_size_bytes: Optional[int] = None) -> bool:
        """
        Загрузка игры
        
        Args:
            game_url: URL страницы игры
            game_title: Название игры для логов
            progress_callback: Функция обратного вызова для отображения прогресса
        
        Returns:
            True если загрузка успешна, False иначе
        """
        self.should_stop = False
        self.progress_callback = progress_callback
        total_size = total_size_bytes
        
        try:
            # Настройка драйвера
            if not self.setup_driver():
                return False
            
            # Очистка папки загрузок
            self.cleanup_downloads()
            
            logger.info(f"Попытка загрузить игру: {game_title}")
            
            # Цикл до успешной загрузки
            max_attempts = 5
            for attempt in range(max_attempts):
                if self.should_stop:
                    break
                    
                logger.info(f"Попытка {attempt + 1} из {max_attempts}")
                
                if self.try_start_download(game_url):
                    # Загрузка началась, ищем файл
                    crdownload_files = list(self.download_dir.glob("*.crdownload"))
                    if crdownload_files:
                        filepath = crdownload_files[0]
                        
                        # Запускаем мониторинг в отдельном потоке
                        monitor_thread = threading.Thread(
                            target=self.monitor_download_progress,
                            args=(filepath, total_size)
                        )
                        monitor_thread.start()
                        
                        # Ждем завершения загрузки
                        while filepath.exists() and not self.should_stop:
                            time.sleep(1)
                        
                        monitor_thread.join()
                        
                        # Проверяем, что файл действительно скачался
                        final_files = [f for f in self.download_dir.glob("*") 
                                     if f.is_file() and not f.name.endswith('.crdownload')]
                        
                        if final_files:
                            logger.info(f"Загрузка завершена: {final_files[0].name}")
                            return True
                        else:
                            logger.warning("Загрузка не завершилась, пробуем снова")
                
                # Если не удалось, сбрасываем и пробуем снова
                if attempt < max_attempts - 1:
                    logger.info("Сбрасываем загрузку и пробуем снова...")
                    try:
                        self.driver.get(self.cancel_url)
                        time.sleep(2)
                    except:
                        pass
            
            logger.error(f"Не удалось загрузить игру после {max_attempts} попыток")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке игры: {e}")
            return False
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
    
    def stop_download(self):
        """Остановка загрузки"""
        self.should_stop = True
        
        if self.driver:
            try:
                self.driver.get(self.cancel_url)
                time.sleep(1)
                self.driver.quit()
            except:
                pass
            self.driver = None
        
        logger.info("Загрузка остановлена")
    
    def get_downloaded_files(self) -> list:
        """Получение списка скачанных файлов"""
        try:
            return [f for f in self.download_dir.glob("*") 
                   if f.is_file() and not f.name.endswith('.crdownload')]
        except:
            return []
