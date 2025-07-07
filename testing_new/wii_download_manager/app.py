from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QStackedWidget, QFileDialog, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from pathlib import Path
import sys
from functools import partial
from models.drive import Drive
from updater import check_for_updates


class AddGamesThread(QThread):
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, drive: Drive, files: list[Path]):
        super().__init__()
        self.drive = drive
        self.files = files

    def run(self):
        total = len(self.files)
        for i, file in enumerate(self.files, start=1):
            try:
                self.drive.add_game(file)
            except Exception:
                pass
            self.progress.emit(i, total)
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TinyWiiBackupManager")
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)
        self.adding_bar = QProgressBar()
        self.adding_label = QLabel()
        self.current_drive = None
        self.games = []
        self._init_drives_page()
        self._init_games_page()
        self._init_add_page()
        self.stacked.setCurrentWidget(self.drives_page)
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        about_action = file_menu.addAction("About")
        about_action.triggered.connect(self.show_about)
        update_action = file_menu.addAction("Check for updates")
        update_action.triggered.connect(lambda: check_for_updates(self))
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

    def show_about(self):
        QMessageBox.information(self, "About", "TinyWiiBackupManager Python Port")

    def _init_drives_page(self):
        self.drives_page = QWidget()
        layout = QVBoxLayout(self.drives_page)
        self.drive_combo = QComboBox()
        refresh_btn = QPushButton("Refresh")
        open_btn = QPushButton("Open")
        refresh_btn.clicked.connect(self.refresh_drives)
        open_btn.clicked.connect(self.open_drive)
        hl = QHBoxLayout()
        hl.addWidget(self.drive_combo)
        hl.addWidget(refresh_btn)
        hl.addWidget(open_btn)
        layout.addLayout(hl)
        self.stacked.addWidget(self.drives_page)
        self.refresh_drives()

    def refresh_drives(self):
        self.drive_combo.clear()
        self.drives = Drive.get_drives()
        for d in self.drives:
            self.drive_combo.addItem(d.name, d)

    def open_drive(self):
        idx = self.drive_combo.currentIndex()
        if idx < 0:
            return
        self.current_drive = self.drive_combo.currentData()
        self.refresh_games()
        self.stacked.setCurrentWidget(self.games_page)

    def _init_games_page(self):
        self.games_page = QWidget()
        v = QVBoxLayout(self.games_page)
        self.drive_label = QLabel()
        self.size_label = QLabel()
        hl = QHBoxLayout()
        hl.addWidget(self.drive_label)
        hl.addWidget(self.size_label)
        add_btn = QPushButton("Add games")
        add_btn.clicked.connect(self.add_games)
        del_btn = QPushButton("Delete selected")
        del_btn.clicked.connect(self.delete_selected)
        select_all = QPushButton("Select all")
        deselect_all = QPushButton("Deselect all")
        select_all.clicked.connect(lambda: self.set_all_checks(True))
        deselect_all.clicked.connect(lambda: self.set_all_checks(False))
        hl2 = QHBoxLayout()
        hl2.addWidget(select_all)
        hl2.addWidget(deselect_all)
        hl2.addWidget(add_btn)
        hl2.addWidget(del_btn)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "Game", "Size (GiB)"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addLayout(hl)
        v.addLayout(hl2)
        v.addWidget(self.table)
        self.stacked.addWidget(self.games_page)

    def _init_add_page(self):
        self.add_page = QWidget()
        v = QVBoxLayout(self.add_page)
        v.addWidget(self.adding_label)
        v.addWidget(self.adding_bar)
        self.stacked.addWidget(self.add_page)

    def refresh_games(self):
        drive = self.current_drive
        self.drive_label.setText(drive.name)
        self.size_label.setText(f"{drive.available_space}/{drive.total_space} GiB")
        self.games = drive.get_games()
        self.table.setRowCount(len(self.games))
        for row, game in enumerate(self.games):
            chk = QCheckBox()
            chk.setChecked(game.checked)
            # Используем partial для правильного захвата переменной game
            chk.stateChanged.connect(partial(self._on_checkbox_changed, game))
            self.table.setCellWidget(row, 0, chk)
            self.table.setItem(row, 1, QTableWidgetItem(game.display_title))
            self.table.setItem(row, 2, QTableWidgetItem(f"{game.size / (1<<30):.2f}"))
            print(f"DEBUG: Added game {game.display_title} with checked={game.checked}")
        self.table.resizeColumnsToContents()

    def _on_checkbox_changed(self, game, state):
        game.checked = state == 2  # Qt.CheckState.Checked = 2
        print(f"DEBUG: Checkbox changed for {game.display_title}, checked: {game.checked}, state: {state}")

    def set_all_checks(self, state: bool):
        for row, game in enumerate(self.games):
            game.checked = state
            w = self.table.cellWidget(row, 0)
            if isinstance(w, QCheckBox):
                w.setChecked(state)

    def add_games(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select games", filter="Wii games (*.iso *.wbfs)")
        if not files:
            return
        paths = [Path(f) for f in files]
        self.thread = AddGamesThread(self.current_drive, paths)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.finish_adding)
        self.thread.start()
        self.adding_bar.setMaximum(len(paths))
        self.stacked.setCurrentWidget(self.add_page)

    def update_progress(self, i, total):
        self.adding_label.setText(f"{i}/{total} Adding games...")
        self.adding_bar.setValue(i)

    def finish_adding(self):
        self.stacked.setCurrentWidget(self.games_page)
        self.refresh_games()

    def delete_selected(self):
        sel = [g for g in self.games if g.checked]
        print(f"DEBUG: Found {len(sel)} selected games")
        for g in self.games:
            print(f"DEBUG: Game {g.display_title} checked: {g.checked}")
        if not sel:
            QMessageBox.information(self, "Info", "No games selected for deletion.")
            return
        res = QMessageBox.question(self, "Delete", f"Are you sure you want to delete {len(sel)} selected games?")
        if res != QMessageBox.StandardButton.Yes:
            return
        for g in sel:
            print(f"DEBUG: Deleting game: {g.display_title}")
            g.delete()
        self.refresh_games()


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
