#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the improved GameCard
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from wii_game_parser import WiiGame
from wii_unified_manager import GameCard

# Create a test game with comprehensive data
test_game = WiiGame(
    title="Super Mario Galaxy",
    region="USA",
    version="1.0",
    languages="EN",
    rating="E",
    serial="RMGE01",
    players="1",
    year="2007",
    file_size="3.7 GB",
    graphics="9.5",
    sound="9.0",
    gameplay="9.8",
    overall="9.4",
    crc="A1B2C3D4",
    verified="Yes",
    box_art="https://vimm.net/image/boxart/3109.jpg",
    disc_art="https://vimm.net/image/discart/3109.jpg",
    detail_url="https://vimm.net/vault/3109"
)

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Game Card")
        self.setGeometry(100, 100, 500, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create the game card
        self.game_card = GameCard(test_game)
        layout.addWidget(self.game_card)
        
        # Apply same background
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8F9FA;
            }
        """)

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
