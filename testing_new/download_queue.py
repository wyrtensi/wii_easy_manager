#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wii Unified Manager 2.3
======================
Главное окно приложения. Требует `wum_style.py`, `download_queue.py`, а также
`wii_game_parser.py` и `wii_game_selenium_downloader.py`.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QMetaObject,
    QRectF,
    Qt,
    Slot,
    QPropertyAnimation,
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

from wum_style import build_style, WII_BLUE, WII_GRAY, WII_WHITE  # type: ignore
from wii_game_parser import WiiGame, WiiGameParser  # type: ignore
from download_queue import DownloadQueue  # type: ignore

###############################################################################
# 🎴 GameCard                                                                #
###############################################################################

class GameCard(QWidget):
    """Displays details and handles download of a single game."""

    def __init__(self, queue: DownloadQueue, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.queue = queue
        self.setFixedWidth(560)

        self._title = QLabel("Выберите игру слева ✨")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_BLUE};"
            "border-radius:16px;padding:12px;font-size:16pt;font-weight:bold;"
        )

        self._cover = QLabel()
        self._cover.setFixedSize(320, 320)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet(
            f"background:{WII_GRAY};border:2px dashed {WII_BLUE};border-radius:24px;"
        )

        self._desc = QLabel("Описание появится здесь…")
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._desc.setStyleSheet(
            f"background:{WII_WHITE};border:2px solid {WII_GRAY};"
            "border-radius:16px;padding:12px;"
        )

        self._btn_dl = QPushButton("⬇️ Скачать")
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.hide()

        lay = QVBoxLayout(self)
        lay.addWidget(self._title)
        lay.addWidget(self._cover, alignment=Qt.AlignCenter)
        lay.addWidget(self._btn_dl, alignment=Qt.AlignCenter)
        lay.addWidget(self._progress)
        lay.addWidget(self._desc)

        self._btn_dl.clicked.connect(self._on_download_clicked)

        queue.download_started.connect(self._on_download_started)
        queue.download_finished.connect(self._on_download_finished)
        queue.progress_changed.connect(self._on_progress)

        self._game: Optional[WiiGame] = None

    # ------------------------------------------------------------------
    def _refresh_button(self):
        if self._game is None:
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
    @Slot()
    def _on_download_clicked(self):
        if self._game:
            self.queue.add(self._game)
            self._refresh_button()

    # ------------------------------------------------------------------
    @Slot(WiiGame)
    def _on_download_started(self, game: WiiGame):
        if self._game and self._game.title == game.title:
            self._progress.show()
            self._progress.setValue(0)
            self._refresh_button()

    # ------------------------------------------------------------------
    @Slot(WiiGame)
    def _on_download_finished(self, game: WiiGame):
        if self._game and self._game.title == game.title:
            self._progress.hide()
            self._refresh_button()

    # ------------------------------------------------------------------
    @Slot(WiiGame, int)
    def _on_progress(self, game: WiiGame, percent: int):
        if self._game and self._game.title == game.title:
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
        self._refresh_button()

###############################################################################
# 🌟 Animated navigation button                                               #
###############################################################################

class AnimatedNavButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)

    def enterEvent(self, event):  # noqa: N802
        if not self.isChecked():
            self._scale(1.05)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        if not self.isChecked():
            self._scale(1.0)
        super().leaveEvent(event)

    def _scale(self, factor: float):
        rect = self.geometry()
        center = rect.center()
        new_rect = QRectF(
            center.x() - rect.width() * factor / 2,
            center.y() - rect.height() * factor / 2,
            rect.width() * factor,
            rect.height() * factor,
        ).toRect()
        self._anim.stop()
        self._anim.setStartValue(rect)
        self._anim.setEndValue(new_rect)
        self._anim.start()

###############################################################################
# 🖥️ Main window                                                             #
###############################################################################

class WiiUnifiedManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎮 Wii Unified Manager 2.3")
        self.resize(1280, 860)
        self.setWindowIcon(QIcon())
        self.setStyleSheet(build_style())

        self.parser = WiiGameParser()
        self.queue = DownloadQueue(self)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QLabel("🎮 Wii Unified Manager")
        header.setProperty("headerTitle", True)
        header.setAlignment(Qt.AlignCenter)
        root.addWidget(header)

        nav = QHBoxLayout()
        self.btn_search = self._nav("🔍 Поиск")
        self.btn_manager = self._nav("💾 Менеджер")
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
        self._connect()

    # ------------------------------------------------------------------
    def _nav(self, text: str) -> QPushButton:
        btn = AnimatedNavButton(text)
        btn.setCheckable(True)
        btn.setProperty("nav", True)
        return btn

    # ------------------------------------------------------------------
    def _build_search_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        h = QHBoxLayout()
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Введите название игры…")
        self.btn_go = QPushButton("🔍 Найти")
        h.addWidget(self.edit_search)
        h.addWidget(self.btn_go)
        v.addLayout(h)

        split = QSplitter(Qt.Horizontal)
        self.list_online = QListWidget()
        self.card = GameCard(self.queue)
        split.addWidget(self.list_online)
        split.addWidget(self.card)
        split.setSizes([400, 800])
        v.addWidget(split)
        return page

    # ------------------------------------------------------------------
    def _build_manager_page(self) -> QWidget:
        p = QWidget()
        lbl = QLabel("💾 Функции менеджера флешки появятся здесь…")
        lbl.setAlignment(Qt.AlignCenter)
        QVBoxLayout(p).addWidget(lbl)
        return p

    # ------------------------------------------------------------------
    def _connect(self):
        self.btn_search.clicked.connect(lambda: self._switch(self.page_search, self.btn_search))
        self.btn_manager.clicked.connect(lambda: self._switch(self.page_manager, self.btn_manager))
        self.btn_go.clicked.connect(self._search)
        self.edit_search.returnPressed.connect(self._search)
        self.list_online.currentRowChanged.connect(self._row_changed)

        self.queue.queue_changed.connect(lambda n: self.status.showMessage(f"Очередь: {n} игр"))
        self.queue.download_started.connect(lambda g: self.status.showMessage(f"⬇️ Скачивание: {g.title}…"))
        self.queue.download_finished.connect(lambda g: self.status.showMessage(f"✅ Завершено: {g.title}"))

    # ------------------------------------------------------------------
    def _switch(self, page: QWidget, btn: QPushButton):
        self.btn_search.setChecked(False)
        self.btn_manager.setChecked(False)
        btn.setChecked
