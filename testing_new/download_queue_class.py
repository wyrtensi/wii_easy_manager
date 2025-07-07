#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Queue Class
==================
Handles game download queue with Qt signals and real downloading
"""

from __future__ import annotations

from queue import Queue, Empty
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer
from wii_game_parser import WiiGame


class DownloadQueue(QObject):
    """Очередь загрузок с Qt сигналами и реальным скачиванием"""

    # Сигналы
    queue_changed = Signal(int)  # количество элементов в очереди
    download_started = Signal(WiiGame)  # начало загрузки
    download_finished = Signal(WiiGame)  # окончание загрузки
    progress_changed = Signal(WiiGame, int)  # прогресс в процентах
    speed_updated = Signal(WiiGame, float, str)  # скорость (MB/s) и время до завершения

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._queue = Queue()
        self._active_downloads = {}  # game_id -> Thread
        self._downloads_in_progress = set()
        self._download_threads = {}  # game_id -> DownloadThread

    def add(self, game: WiiGame):
        """Добавить игру в очередь"""
        if hasattr(game, 'status'):
            if game.status in {"queued", "downloading", "downloaded"}:
                return
        
        # Устанавливаем статус
        game.status = "queued"
        
        self._queue.put(game)
        self.queue_changed.emit(self._queue.qsize())
        
        # Запускаем скачивание, если не идет другое
        if not self._downloads_in_progress:
            QTimer.singleShot(100, self._start_next_download)  # Небольшая задержка

    def _start_next_download(self):
        """Запустить следующую загрузку"""
        try:
            game = self._queue.get_nowait()
            self._downloads_in_progress.add(game.title)
            
            # Создаем поток загрузки
            from download_thread import DownloadThread
            download_thread = DownloadThread(game)
            
            # Подключаем сигналы - фиксируем захват game в замыкании
            game_ref = game  # Создаем явную ссылку на игру
            download_thread.progress_updated.connect(
                lambda downloaded, total, speed, eta, g=game_ref: self._on_progress_updated(g, downloaded, total, speed, eta)
            )
            download_thread.download_finished.connect(
                lambda success, message, g=game_ref: self._on_download_finished(g, success, message)
            )
            
            self._download_threads[game.title] = download_thread
            
            # Запускаем загрузку
            game.status = "downloading"
            self.download_started.emit(game)
            download_thread.start()
            
        except Empty:
            pass

    def _on_progress_updated(self, game: WiiGame, downloaded: int, total: int, speed: float, eta: str):
        """Обработка обновления прогресса"""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_changed.emit(game, percent)
        else:
            # Индетерминированный прогресс - показываем анимированный индикатор
            # Используем время для создания пульсирующего эффекта
            import time
            pulse = int((time.time() * 2) % 100)  # Пульсация от 0 до 100
            self.progress_changed.emit(game, pulse)
        
        self.speed_updated.emit(game, speed, eta)

    def _on_download_finished(self, game: WiiGame, success: bool, message: str):
        """Обработка завершения загрузки"""
        # Удаляем из активных загрузок
        self._downloads_in_progress.discard(game.title)
        if game.title in self._download_threads:
            del self._download_threads[game.title]
        
        # Устанавливаем статус
        game.status = "downloaded" if success else "error"
        
        self.download_finished.emit(game)
        self.queue_changed.emit(self._queue.qsize())
        
        # Запускаем следующую загрузку через 2 секунды
        if not self._queue.empty():
            QTimer.singleShot(2000, self._start_next_download)

    def get_queue_size(self) -> int:
        """Получить размер очереди"""
        return self._queue.qsize()

    def is_empty(self) -> bool:
        """Проверить, пуста ли очередь"""
        return self._queue.empty()

    def stop_all_downloads(self):
        """Остановить все загрузки"""
        for thread in self._download_threads.values():
            if hasattr(thread, 'stop'):
                thread.stop()
        self._download_threads.clear()
        self._downloads_in_progress.clear()
