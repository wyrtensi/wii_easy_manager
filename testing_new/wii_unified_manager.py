#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wii Unified Manager 2.4
======================
Главный исполняемый файл приложения с новым Wii‑стилем, поиском онлайн игр и
загрузками. Требует:
  • wum_style.py          — палитра + QSS
  • download_queue.py     — очередь загрузок
  • wii_game_parser.py    — парсер страниц (из прежней версии)
  • wii_game_selenium_downloader.py — реальный загрузчик
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Slot,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# ────────────────────────────────────────────────────────────────────────────
# Local modules
# ────────────────────────────────────────────────────────────────────────────
from wum_style import build_style, WII_BLUE, WII_GRAY, WII_WHITE  # type: ignore
from download_queue import DownloadQueue  # type: ignore
from wii_game_parser import WiiGame, WiiGameParser  # type: ignore

###############################################################################
# 🎴 GameCard                                                                #
###############################################################################

class GameCard(QWidget):
    """Отображает подробности об игре и кнопку скачивания."""

    def __init__(self, queue: DownloadQueue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue = queue
        self.setFixedWidth(560)

        # ─── заголовок
        self._title = QLabel("Выберите игру слева ✨")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_BLUE};"
            "border-radius:16px;padding:12px;font-size:16pt;font-weight:bold;"
        )

        # ─── обложка
        self._cover = QLabel()
        self._cover.setFixedSize(320, 320)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet(
            f"background:{WII_GRAY};border:2px dashed {WII_BLUE};border-radius:24px;"
        )

        # ─── описание
        self._desc = QLabel("Описание появится здесь…")
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._desc.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_GRAY};"
            "border-radius:16px;padding:12px;"
        )

        # ─── кнопка скачивания + прогресс
        self._btn_dl = QPushButton("⬇️ Скачать")
        self._progress = QProgressBar()
        self._progress.hide()

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._cover, alignment=Qt.AlignCenter)
        lay.addWidget(self._btn_dl, alignment=Qt.AlignCenter)
        lay.addWidget(self._progress)
        lay.addWidget(self._desc)

        # Connect signals
        self._btn_dl.clicked.connect(self._do_download)
        queue.download_started.connect(self._on_dl_start)
        queue.download_finished.connect(self._on_dl_finish)
        queue.progress_changed.connect(self._on_progress)

        self._game: Optional[WiiGame] = None

    # ------------------------------------------------------------------
    def _refresh_btn(self):
        if not self._game:
            self._btn_dl.setEnabled(False)
            self._btn_dl.setText("⬇️ Скачать")
            return
        status = getattr(self._game, "status", "")
        self._btn_dl.setEnabled(status not in {"queued", "downloading", "downloaded"})
        self._btn_dl.setText({
            "queued": "⌛ В очереди",
            "downloading": "⬇️ Скачивается…",
            "downloaded": "✅ Скачано",
        }.get(status, "⬇️ Скачать"))

    # ------------------------------------------------------------------
    def _do_download(self):
        if self._game:
            self.queue.add(self._game)
            self._refresh_btn()

    # ------------------------------------------------------------------
    @Slot(WiiGame)
    def _on_dl_start(self, g: WiiGame):
        if self._game and g.title == self._game.title:
            self._progress.show()
            self._progress.setValue(0)
            self._refresh_btn()

    @Slot(WiiGame)
    def _on_dl_finish(self, g: WiiGame):
        if self._game and g.title == self._game.title:
            self._progress.hide()
            self._refresh_btn()

    @Slot(WiiGame, int)
    def _on_progress(self, g: WiiGame, percent: int):
        if self._game and g.title == self._game.title:
            self._progress.setValue(percent)

    # ------------------------------------------------------------------
    def update_game(self, game: WiiGame):
        self._game = game
        self._title.setText(game.title)
        self._desc.setText(game.description or "Описание отсутствует.")
        if game.cover_path and Path(game.cover_path).exists():
            pix = QPixmap(game.cover_path).scaled(
                self._cover.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._cover.setPixmap(pix)
        else:
            self._cover.setText("🖼️")
        self._refresh_btn()

###############################################################################
# 🌟 Animated navigation button                                               #
###############################################################################

class AnimatedNavButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setProperty("nav", True)
        self.setCheckable(True)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def enterEvent(self, e):  # noqa: N802
        if not self.isChecked():
            self._scale(1.05)
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        if not self.isChecked():
            self._scale(1.0)
        super().leaveEvent(e)

    def _scale(self, k: float):
        r = self.geometry()
        c = r.center()
        self._anim.stop()
        self._anim.setStartValue(r)
        self._anim.setEndValue(QRectF(c.x()-r.width()*k/2, c.y()-r.height()*k/2, r.width()*k, r.height()*k).toRect())
        self._anim.start()

###############################################################################
# 🖥️ Main window                                                             #
###############################################################################

class WiiUnifiedManager(QMainWindow):
    """Главное окно приложения."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("🎮 Wii Unified Manager 2.4")
        self.resize(1280, 860)
        self.setWindowIcon(QIcon())
        self.setStyleSheet(build_style())

        # Services
        self.parser = WiiGameParser()
        self.queue = DownloadQueue(self)

        # UI layout
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QLabel("🎮 Wii Unified Manager")
        header.setProperty("headerTitle", True)
        header.setAlignment(Qt.AlignCenter)
        root.addWidget(header)

        nav = QHBoxLayout()
        self.btn_search = AnimatedNavButton("🔍 Поиск")
        self.btn_manager = AnimatedNavButton("💾 Менеджер")
        self.btn_search.setChecked(True)
        nav.addStretch()
        nav.addWidget(self.btn_search)
        nav.addWidget(self.btn_manager)
        nav.addStretch()
        root.addLayout(nav)

        self.stack = QStackedWidget()
        self.page_search = self._build_search_page()
        self.page_manager = self._build_manager_page()
        self.stack.addWidget(self.page_search)
        self.stack.addWidget(self.page_manager)
        root.addWidget(self.stack)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Готов к работе 🔋")

        self._games: List[WiiGame] = []
        self._connect_signals()

    # ------------------------------------------------------------------
    def _build_search_page(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)

        hbox = QHBoxLayout()
        self.edit_query = QLineEdit()
        self.edit_query.setPlaceholderText("Введите название игры…")
        self.btn_go = QPushButton("🔍 Найти")
        hbox.addWidget(self.edit_query)
        hbox.addWidget(self.btn_go)
        vbox.addLayout(hbox)

        splitter = QSplitter(Qt.Horizontal)
        self.list_results = QListWidget()
        self.card = GameCard(self.queue)
        splitter.addWidget(self.list_results)
        splitter.addWidget(self.card)
        splitter.setSizes([400, 800])
        vbox.addWidget(splitter)
        return page

    # ------------------------------------------------------------------
    def _build_manager_page(self) -> QWidget:
        page = QWidget()
        label = QLabel("💾 Функции менеджера флешки появятся здесь…")
        label.setAlignment(Qt.AlignCenter)
        QVBoxLayout(page).addWidget(label)
        return page

    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.btn_search.clicked.connect(lambda: self._switch_page(self.page_search, self.btn_search))
        self.btn_manager.clicked.connect(lambda: self._switch_page(self.page_manager, self.btn_manager))
        self.btn_go.clicked.connect(self._do_search)
        self.edit_query.returnPressed.connect(self._do_search)
        self.list_results.currentRowChanged.connect(self._row_changed)

        # Queue → status
        self.queue.queue_changed.connect(lambda n: self.status.showMessage(f"Очередь: {n} игр"))
        self.queue.download_started.connect(lambda g: self.status.showMessage(f"⬇️ Скачивание: {g.title}…"))
        self.queue.download_finished.connect(lambda g: self.status.showMessage(f"✅ Завершено: {g.title}"))

    # ------------------------------------------------------------------
    def _switch_page(self, page: QWidget, btn: QPushButton):
        self.btn_search.setChecked(False)
        self.btn_manager.setChecked(False)
        btn.setChecked(True)
        self.stack.setCurrentWidget(page)

    # ------------------------------------------------------------------
    def _do_search(self):
        query = self.edit_query.text().strip()
        if not query:
            return
        self.status.showMessage(f"Поиск «{query}»…")

        def worker():
            games = self.parser.parse_search_results_from_query(query)  # type: ignore[attr-defined]
            QApplication.instance().postEvent(self, lambda: self._populate_list(games))

        import threading

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    def _populate_list(self, games: List[WiiGame]):
        self._games = games
        self.list_results.clear()
        for g in games:
            item = QListWidgetItem(f"🎮 {g.title}")
            self.list_results.addItem(item)
        if games:
            self.list_results.setCurrentRow(0)
        self.status.showMessage(f"Найдено {len(games)} игр")

    # ------------------------------------------------------------------
    def _row_changed(self, row: int):
        if 0 <= row < len(self._games):
            self.card.update_game(self._games[row])

###############################################################################
# 🚀 main                                                                    #
###############################################################################

def main():
    app = QApplication(sys.argv)
    win = WiiUnifiedManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
